#!/usr/bin/env python3

import argparse
import json
from datetime import datetime, timezone
from os import environ
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

# Load environment variables from .env file
load_dotenv()

# Database connection parameters
DB_PARAMS = {
    "database": environ.get("DRZEWO_DB", "drzewo"),
    "user": environ.get("DRZEWO_DB_USER", "greg"),
    "password": environ.get("DRZEWO_DB_PW"),
    "host": environ.get("DRZEWO_DB_HOST", "localhost"),
    "port": environ.get("DRZEWO_DB_PORT", "5432"),
}

DEFAULT_BATCH_SIZE = 1000
PROGRESS_INTERVAL = 10000

# Mappings for city-specific handlers
CITY_HANDLERS = {
    "toronto": {
        "source_name": "Toronto Open Data Street Trees",
        "loader": "load_toronto_data",
        "enrichments": ["wikipedia_links", "human_readable_names"],
    },
    "ottawa": {
        "source_name": "Ottawa Open Data Tree Inventory",
        "loader": "load_ottawa_data",
        "enrichments": ["wikipedia_links"],
    },
    "montreal": {
        "source_name": "Montreal Open Data Tree Inventory",
        "loader": "load_montreal_data",
        "enrichments": ["wikipedia_links"],
    },
    "calgary": {
        "source_name": "Calgary Open Data Tree Inventory",
        "loader": "load_calgary_data",
        "enrichments": ["tree_condition", "wikipedia_links"],
    },
    "waterloo": {
        "source_name": "Waterloo Open Data Tree Inventory",
        "loader": "load_waterloo_data",
        "enrichments": [],
    },
    "boston": {
        "source_name": "Boston Open Data Tree Inventory",
        "loader": "load_boston_data",
        "enrichments": [],
    },
    "markham": {
        "source_name": "Markham Open Data Street Trees",
        "loader": "load_markham_data",
        "enrichments": [],
    },
    "oakville": {
        "source_name": "Oakville Parks Tree Forestry",
        "loader": "load_oakville_data",
        "enrichments": [],
    },
    "peterborough": {
        "source_name": "Peterborough Open Data Tree Inventory",
        "loader": "load_peterborough_data",
        "enrichments": [],
    },
}


def connect_db():
    """Create and return a database connection."""
    return psycopg2.connect(**DB_PARAMS)


def ensure_import_runs_table(cursor):
    """Create the import audit table if it does not already exist."""
    cursor.execute("SELECT to_regclass('public.import_runs');")
    if cursor.fetchone()[0] is not None:
        return
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_runs (
        id BIGSERIAL PRIMARY KEY,
        city TEXT NOT NULL,
        source_name TEXT NOT NULL,
        source_file TEXT NOT NULL,
        refresh_mode BOOLEAN NOT NULL DEFAULT FALSE,
        row_count INTEGER,
        status TEXT NOT NULL,
        error_message TEXT,
        started_at TIMESTAMPTZ NOT NULL,
        finished_at TIMESTAMPTZ NOT NULL
    );
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_import_runs_city_finished_at
    ON import_runs (city, finished_at DESC);
    """)


def delete_city_rows(cursor, source_name):
    """Delete all rows for one city source before a refresh load."""
    cursor.execute("DELETE FROM street_trees WHERE source = %s;", (source_name,))


def count_city_rows(cursor, source_name):
    """Return total rows currently stored for the source."""
    cursor.execute("SELECT COUNT(*) FROM street_trees WHERE source = %s;", (source_name,))
    return cursor.fetchone()[0]


def record_import_run(
    cursor,
    *,
    city,
    source_name,
    source_file,
    refresh_mode,
    row_count,
    status,
    started_at,
    finished_at,
    error_message=None,
):
    """Insert one import audit row."""
    cursor.execute(
        """
        INSERT INTO import_runs (
            city, source_name, source_file, refresh_mode, row_count, status,
            error_message, started_at, finished_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        );
        """,
        (
            city,
            source_name,
            source_file,
            refresh_mode,
            row_count,
            status,
            error_message,
            started_at,
            finished_at,
        ),
    )


def log_failed_import(city, city_config, filename, refresh_mode, started_at, error_message):
    """Persist failure metadata after the main transaction rolls back."""
    failure_conn = connect_db()
    try:
        failure_cursor = failure_conn.cursor()
        ensure_import_runs_table(failure_cursor)
        record_import_run(
            failure_cursor,
            city=city,
            source_name=city_config["source_name"],
            source_file=str(Path(filename).resolve()),
            refresh_mode=refresh_mode,
            row_count=None,
            status="failed",
            error_message=error_message,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
        failure_conn.commit()
        failure_cursor.close()
    finally:
        failure_conn.close()


def load_city_data(cursor, city, city_config, filename, batch_size):
    """Dispatch to the configured city loader."""
    loader = globals()[city_config["loader"]]
    loader(cursor, filename, batch_size=batch_size)


def point_to_multipoint_json(geometry):
    """Normalize Point geometries to the MultiPoint schema shape."""
    normalized = geometry
    if normalized and normalized.get("type") == "Point":
        normalized = {
            "type": "MultiPoint",
            "coordinates": [normalized.get("coordinates")],
        }
    return json.dumps(normalized)


def load_toronto_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Toronto data using batched inserts."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, structid, address, streetname, crossstreet1, crossstreet2, suffix,
        unit_number, tree_position_number, site, ward, botanical_name, common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        rows.append(toronto_row_tuple(feature))
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Toronto features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def toronto_row_tuple(feature):
    """Build one Toronto insert row."""
    source = "Toronto Open Data Street Trees"
    properties = feature["properties"]
    return (
        source,
        properties.get("OBJECTID"),
        properties.get("STRUCTID"),
        properties.get("ADDRESS"),
        properties.get("STREETNAME"),
        properties.get("CROSSSTREET1"),
        properties.get("CROSSSTREET2"),
        properties.get("SUFFIX"),
        properties.get("UNIT_NUMBER"),
        properties.get("TREE_POSITION_NUMBER"),
        properties.get("SITE"),
        properties.get("WARD"),
        properties.get("BOTANICAL_NAME"),
        properties.get("COMMON_NAME"),
        properties.get("DBH_TRUNK"),
        point_to_multipoint_json(feature["geometry"]),
    )


def load_ottawa_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Ottawa data using batched inserts."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, address, streetname, botanical_name, common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        rows.append(ottawa_row_tuple(feature))
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Ottawa features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def ottawa_row_tuple(feature):
    """Build one Ottawa insert row."""
    source = "Ottawa Open Data Tree Inventory"
    properties = feature["properties"]
    return (
        source,
        properties.get("OBJECTID"),
        properties.get("ADDNUM"),
        properties.get("ADDSTR"),
        properties.get("SPECIES"),
        properties.get("SPECIES"),
        properties.get("DBH"),
        point_to_multipoint_json(feature["geometry"]),
    )


def load_montreal_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Montreal data using batched inserts."""
    import csv

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, ward, streetname, site, botanical_name, common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326))
    """

    rows = []
    with open(filename, "r") as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader, start=1):
            row_tuple = montreal_row_tuple(row)
            if row_tuple is None:
                continue
            rows.append(row_tuple)
            if len(rows) >= batch_size:
                _flush_batch(cursor, sql_query, rows, template, batch_size)
            if idx % PROGRESS_INTERVAL == 0:
                print(f"Processed {idx} Montreal rows...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def montreal_row_tuple(row):
    """Build one Montreal insert row."""
    source = "Montreal Open Data Tree Inventory"
    if row["DHP"]:
        dbh = round(float(row['DHP']))
    else:
        dbh = None
    longitude = row["Longitude"]
    latitude = row["Latitude"]
    if not longitude or not latitude:
        return
    return (
        source,
        row["EMP_NO"],
        f"{row['ARROND_NOM']}",
        row["LOCALISATION"],
        row["Emplacement"],
        row["Essence_latin"],
        f"{row['Essence_fr']} ({row['ESSENCE_ANG']})",
        dbh,
        longitude,
        latitude,
    )


def load_calgary_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Calgary data using batched inserts."""
    import csv

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, structid, common_name, botanical_name,
        dbh_trunk, address, streetname, site, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
    """

    rows = []
    with open(filename, "r") as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader, start=1):
            rows.append(calgary_row_tuple(row))
            if len(rows) >= batch_size:
                _flush_batch(cursor, sql_query, rows, template, batch_size)
            if idx % PROGRESS_INTERVAL == 0:
                print(f"Processed {idx} Calgary rows...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def calgary_row_tuple(row):
    """Build one Calgary insert row using only columns present in the shared schema."""
    species_parts = [row.get("GENUS"), row.get("SPECIES"), row.get("CULTIVAR")]
    botanical_name = " ".join(part for part in species_parts if part and part.strip()).strip()
    wam_id = row.get("WAM_ID", "")
    objectid = "".join(ch for ch in wam_id if ch.isdigit())
    if not objectid:
        objectid = "".join(ch for ch in row.get("TREE_ASSET_CD", "") if ch.isdigit())
    if not objectid:
        raise ValueError(f"Calgary row is missing a numeric identifier: {row.get('TREE_ASSET_CD')}")
    dbh_raw = row.get("DBH_CM")
    dbh_trunk = None
    if dbh_raw not in (None, ""):
        try:
            dbh_trunk = round(float(dbh_raw))
        except (TypeError, ValueError):
            dbh_trunk = None
    return (
        "Calgary Open Data Tree Inventory",
        int(objectid),
        row.get("TREE_ASSET_CD"),
        row.get("COMMON_NAME"),
        botanical_name or None,
        dbh_trunk,
        row.get("LOCATION_DETAIL"),
        row.get("COMM_CODE"),
        row.get("ASSET_SUBTYPE") or row.get("ASSET_TYPE"),
        row["POINT"],
    )


def enrich_data(cursor, city_config):
    """Apply data enrichments like Wikipedia links or human-readable names."""
    if "wikipedia_links" in city_config["enrichments"]:
        # Example: Add Wikipedia links
        cursor.execute("""
        UPDATE street_trees
        SET wikipedia_url = sub.wikipedia_url
        FROM species_links sub
        WHERE street_trees.common_name = sub.common_name;
        """)
    if "human_readable_names" in city_config["enrichments"]:
        # Example: Add human-readable names
        cursor.execute("""
        UPDATE street_trees
        SET common_name = sub.readable_name
        FROM species_names sub
        WHERE street_trees.common_name = sub.original_common_name;
        """)


def load_waterloo_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Waterloo data using batched inserts."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, common_name, botanical_name, address, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        rows.append(waterloo_row_tuple(feature))
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Waterloo features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def waterloo_row_tuple(feature):
    """Build one Waterloo insert row."""
    source = "Waterloo Open Data Tree Inventory"
    properties = feature["properties"]
    dbh_trunk = properties.get("DBH_CM")
    if dbh_trunk == "null":
        dbh_trunk = None
    return (
        source,
        properties.get("ASSET_ID"),
        properties.get("COM_NAME"),
        properties.get("LATIN_NAME"),
        properties.get("ADDRESS"),
        dbh_trunk,
        point_to_multipoint_json(feature["geometry"]),
    )


def _flush_batch(cursor, sql_query, rows, template, batch_size):
    """Insert buffered rows using batched VALUES clauses."""
    if not rows:
        return
    execute_values(cursor, sql_query, rows, template=template, page_size=batch_size)
    rows.clear()


def load_boston_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Boston data and insert it into the database."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, address, streetname, suffix, ward,
        botanical_name, common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = boston_row_tuple(feature)
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Boston features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def boston_row_tuple(feature):
    """Build one Boston insert row."""
    source = "Boston Open Data Tree Inventory"
    properties = feature["properties"]
    geometry = feature["geometry"]

    # Schema currently stores MultiPoint geometries.
    if geometry and geometry.get("type") == "Point":
        geometry = {
            "type": "MultiPoint",
            "coordinates": [geometry.get("coordinates")],
        }

    objectid = properties.get("OBJECTID")
    address = str(properties.get("address") or "").strip() or None
    streetname = properties.get("street")
    suffix = properties.get("suffix")
    ward = properties.get("neighborhood")
    botanical_name = properties.get("spp_bot")
    common_name = properties.get("spp_com")
    dbh_raw = properties.get("dbh")
    dbh_trunk = None

    if dbh_raw not in (None, "", "--"):
        try:
            dbh_trunk = round(float(dbh_raw))
        except (TypeError, ValueError):
            dbh_trunk = None

    return (
        source,
        objectid,
        address,
        streetname,
        suffix,
        ward,
        botanical_name,
        common_name,
        dbh_trunk,
        json.dumps(geometry),
    )


def load_markham_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Markham data and insert it into the database."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, streetname, crossstreet1, crossstreet2, site, ward,
        botanical_name, common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = markham_row_tuple(feature)
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Markham features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def markham_row_tuple(feature):
    """Build one Markham insert row."""
    source = "Markham Open Data Street Trees"
    properties = feature["properties"]
    geometry = feature["geometry"]

    # Schema currently stores MultiPoint geometries.
    if geometry and geometry.get("type") == "Point":
        geometry = {
            "type": "MultiPoint",
            "coordinates": [geometry.get("coordinates")],
        }

    objectid = properties.get("OBJECTID")
    streetname = properties.get("ONSTREET")
    crossstreet1 = properties.get("XSTREET1")
    crossstreet2 = properties.get("XSTREET2")
    site = properties.get("RDSECTYPE")
    ward = properties.get("MUNICIPALITY")
    botanical_name = properties.get("SPECIES")
    common_name = properties.get("COMMONNAME")
    dbh_raw = properties.get("CURRENTDBH")
    dbh_trunk = None

    if dbh_raw not in (None, "", "--"):
        try:
            dbh_trunk = round(float(dbh_raw))
        except (TypeError, ValueError):
            dbh_trunk = None

    return (
        source,
        objectid,
        streetname,
        crossstreet1,
        crossstreet2,
        site,
        ward,
        botanical_name,
        common_name,
        dbh_trunk,
        json.dumps(geometry),
    )


def load_oakville_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Oakville data and insert it into the database."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, address, streetname, crossstreet1, site, ward,
        botanical_name, common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = oakville_row_tuple(feature)
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Oakville features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def oakville_row_tuple(feature):
    """Build one Oakville insert row."""
    source = "Oakville Parks Tree Forestry"
    properties = feature["properties"]
    geometry = feature["geometry"]

    # Schema currently stores MultiPoint geometries.
    if geometry and geometry.get("type") == "Point":
        geometry = {
            "type": "MultiPoint",
            "coordinates": [geometry.get("coordinates")],
        }

    def clean_text(value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        return text

    objectid = properties.get("OBJECTID")
    street_number = clean_text(properties.get("STREET_NUMBER"))
    street_name = clean_text(properties.get("STREET_NAME"))
    address = " ".join(part for part in [street_number, street_name] if part) or None
    streetname = street_name
    crossstreet1 = clean_text(properties.get("CROSS_ROADS"))
    site = clean_text(properties.get("LOCSITE"))
    ward = clean_text(properties.get("FORESTRY_ZONE"))
    species = clean_text(properties.get("SPECIES"))
    common_name = species
    botanical_name = None
    dbh_trunk = properties.get("DBH")

    if species and " - " in species:
        common_part, botanical_part = species.split(" - ", 1)
        common_name = clean_text(common_part)
        botanical_name = clean_text(botanical_part)

    return (
        source,
        objectid,
        address,
        streetname,
        crossstreet1,
        site,
        ward,
        botanical_name,
        common_name,
        dbh_trunk,
        json.dumps(geometry),
    )


def load_peterborough_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Peterborough data and insert it into the database."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, address, streetname, site, ward,
        botanical_name, common_name, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = peterborough_row_tuple(feature)
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Peterborough features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def peterborough_row_tuple(feature):
    """Build one Peterborough insert row."""
    source = "Peterborough Open Data Tree Inventory"
    properties = feature["properties"]
    geometry = feature["geometry"]

    # Schema currently stores MultiPoint geometries.
    if geometry and geometry.get("type") == "Point":
        geometry = {
            "type": "MultiPoint",
            "coordinates": [geometry.get("coordinates")],
        }

    address = properties.get("ADDNUM")
    streetname = properties.get("STREET")
    site = properties.get("INVENTORY_LOC") or properties.get("TREE_LOCATION")
    ward = str(properties.get("ZONE")) if properties.get("ZONE") is not None else None

    return (
        source,
        properties.get("OBJECTID"),
        address,
        streetname,
        site,
        ward,
        properties.get("BOTANICAL"),
        properties.get("COMMON"),
        json.dumps(geometry),
    )


def main():
    parser = argparse.ArgumentParser(description="Tree Data Import and Enrichment CLI")
    parser.add_argument("city", choices=CITY_HANDLERS.keys(), help="City to process")
    parser.add_argument("--file", required=True, help="Path to the data file")
    parser.add_argument("--enrich", action="store_true", help="Apply data enrichments")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Delete existing rows for this city source before loading",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Rows per batched INSERT for large imports (default: 1000)",
    )

    args = parser.parse_args()
    city = args.city
    filename = args.file
    apply_enrichments = args.enrich
    refresh_mode = args.refresh
    batch_size = max(1, args.batch_size)

    city_config = CITY_HANDLERS[city]
    source_name = city_config["source_name"]
    source_file = str(Path(filename).resolve())
    started_at = datetime.now(timezone.utc)

    conn = connect_db()
    try:
        cursor = conn.cursor()
        ensure_import_runs_table(cursor)

        print(f"Loading data for {city}...")
        if refresh_mode:
            print(f"Refreshing existing rows for {source_name}...")
            delete_city_rows(cursor, source_name)

        load_city_data(cursor, city, city_config, filename, batch_size)

        if apply_enrichments:
            print(f"Applying enrichments for {city}...")
            enrich_data(cursor, city_config)

        row_count = count_city_rows(cursor, source_name)
        record_import_run(
            cursor,
            city=city,
            source_name=source_name,
            source_file=source_file,
            refresh_mode=refresh_mode,
            row_count=row_count,
            status="completed",
            error_message=None,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
        )
        conn.commit()
        # Refresh table stats after bulk writes so nearest-neighbor plans stay fast.
        try:
            analyze_cursor = conn.cursor()
            analyze_cursor.execute("ANALYZE street_trees;")
            analyze_cursor.close()
        except Exception as analyze_error:
            print(f"ANALYZE failed (data import still committed): {analyze_error}")

        print("Data import and enrichment completed successfully.")

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
        try:
            log_failed_import(city, city_config, filename, refresh_mode, started_at, str(e))
        except Exception as log_error:
            print(f"Failed to write import_runs failure entry: {log_error}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
