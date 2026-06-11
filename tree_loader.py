#!/usr/bin/env python3

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from os import environ
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from data_management import latest_archived_dataset

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
SPECIES_SEED_DIR = Path(__file__).resolve().parent / "seeds"
SPECIES_CATALOG_FILE = SPECIES_SEED_DIR / "species.csv"
SPECIES_ALIASES_FILE = SPECIES_SEED_DIR / "species_aliases.csv"
_SPECIES_CATALOG_CACHE = None

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
    "mississauga": {
        "source_name": "Mississauga City-Owned Tree Inventory",
        "loader": "load_mississauga_data",
        "enrichments": [],
    },
    "san_francisco": {
        "source_name": "San Francisco Street Tree Inventory",
        "loader": "load_san_francisco_data",
        "enrichments": ["wikipedia_links"],
    },
    "madison_wi": {
        "source_name": "Madison Urban Forestry Street Trees",
        "loader": "load_madison_data",
        "enrichments": ["wikipedia_links"],
    },
    "geneva": {
        "source_name": "Geneva Cantonal Tree Inventory",
        "loader": "load_geneva_data",
        "enrichments": ["wikipedia_links"],
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


def ensure_street_tree_species_columns(cursor):
    """Create species enrichment columns needed by newer loaders."""
    if not table_column_exists(cursor, "street_trees", "original_common_name"):
        cursor.execute("""
        ALTER TABLE street_trees
            ADD COLUMN original_common_name TEXT;
        """)
    if not table_column_exists(cursor, "street_trees", "species_id"):
        cursor.execute("""
        ALTER TABLE street_trees
            ADD COLUMN species_id BIGINT REFERENCES species(id);
        """)
    cursor.execute("""
    UPDATE street_trees
    SET original_common_name = common_name
    WHERE original_common_name IS NULL
      AND common_name IS NOT NULL;
    """)
    cursor.execute("SELECT to_regclass('public.idx_street_trees_species_id');")
    if cursor.fetchone()[0] is None:
        cursor.execute("""
        CREATE INDEX idx_street_trees_species_id
        ON street_trees (species_id);
        """)


def ensure_species_tables(cursor):
    """Create normalized species catalog tables if they do not already exist."""
    cursor.execute("SELECT to_regclass('public.species');")
    if cursor.fetchone()[0] is None:
        cursor.execute("""
        CREATE TABLE species (
            id BIGSERIAL PRIMARY KEY,
            species_key TEXT NOT NULL UNIQUE,
            canonical_botanical_name TEXT NOT NULL UNIQUE,
            display_common_name TEXT NOT NULL,
            wikipedia_url TEXT
        );
        """)
    cursor.execute("SELECT to_regclass('public.species_name_alias');")
    if cursor.fetchone()[0] is None:
        cursor.execute("""
        CREATE TABLE species_name_alias (
            id BIGSERIAL PRIMARY KEY,
            species_id BIGINT NOT NULL REFERENCES species(id) ON DELETE CASCADE,
            alias TEXT NOT NULL,
            normalized_alias TEXT NOT NULL,
            name_kind TEXT NOT NULL,
            locale TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            confidence TEXT NOT NULL DEFAULT 'curated',
            UNIQUE (normalized_alias, name_kind, locale, source)
        );
        """)


def table_column_exists(cursor, table_name, column_name):
    """Return whether a public table column exists."""
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s
        );
        """,
        (table_name, column_name),
    )
    return cursor.fetchone()[0]


def seed_species_catalog(cursor):
    """Upsert the checked-in species seed catalog and aliases."""
    catalog = load_species_catalog()
    species_rows = [
        (
            row["species_key"],
            row["canonical_botanical_name"],
            row["display_common_name"],
            row["wikipedia_url"],
        )
        for row in catalog["species_rows"]
    ]
    execute_values(
        cursor,
        """
        INSERT INTO species (
            species_key, canonical_botanical_name, display_common_name, wikipedia_url
        ) VALUES %s
        ON CONFLICT (species_key) DO UPDATE SET
            canonical_botanical_name = EXCLUDED.canonical_botanical_name,
            display_common_name = EXCLUDED.display_common_name,
            wikipedia_url = EXCLUDED.wikipedia_url;
        """,
        species_rows,
        page_size=DEFAULT_BATCH_SIZE,
    )

    alias_rows = []
    seen_alias_keys = set()

    def add_alias_row(species_key, alias, name_kind, locale, source, confidence):
        normalized_alias = normalize_species_text(alias)
        alias_key = (normalized_alias, name_kind, locale, source)
        if alias_key in seen_alias_keys:
            return
        seen_alias_keys.add(alias_key)
        alias_rows.append(
            (
                species_key,
                alias,
                normalized_alias,
                name_kind,
                locale,
                source,
                confidence,
            )
        )

    for row in catalog["species_rows"]:
        add_alias_row(
            row["species_key"],
            row["canonical_botanical_name"],
            "botanical",
            "",
            "",
            "curated",
        )
    for row in catalog["alias_rows"]:
        add_alias_row(
            row["species_key"],
            row["alias"],
            row["name_kind"],
            row["locale"],
            row["source"],
            row["confidence"],
        )
    execute_values(
        cursor,
        """
        INSERT INTO species_name_alias (
            species_id, alias, normalized_alias, name_kind, locale, source, confidence
        )
        SELECT
            species.id,
            data.alias,
            data.normalized_alias,
            data.name_kind,
            data.locale,
            data.source,
            data.confidence
        FROM (VALUES %s) AS data (
            species_key, alias, normalized_alias, name_kind, locale, source, confidence
        )
        JOIN species ON species.species_key = data.species_key
        WHERE TRUE
        ON CONFLICT (normalized_alias, name_kind, locale, source) DO UPDATE SET
            species_id = EXCLUDED.species_id,
            alias = EXCLUDED.alias,
            confidence = EXCLUDED.confidence;
        """,
        alias_rows,
        page_size=DEFAULT_BATCH_SIZE,
    )


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
        unit_number, tree_position_number, site, ward, botanical_name, common_name,
        original_common_name, species_id, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    (SELECT id FROM species WHERE species_key = %s),
    %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
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
    botanical_name = properties.get("BOTANICAL_NAME")
    common_name, original_common_name, species_key = resolved_species_values(
        properties.get("COMMON_NAME"), botanical_name, source
    )
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
        botanical_name,
        common_name,
        original_common_name,
        species_key,
        properties.get("DBH_TRUNK"),
        point_to_multipoint_json(feature["geometry"]),
    )


def load_ottawa_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Ottawa data using batched inserts."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, address, streetname, botanical_name, common_name,
        original_common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
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
    species = properties.get("SPECIES")
    common_name, original_common_name = common_name_values(species, species)
    return (
        source,
        properties.get("OBJECTID"),
        properties.get("ADDNUM"),
        properties.get("ADDSTR"),
        species,
        common_name,
        original_common_name,
        properties.get("DBH"),
        point_to_multipoint_json(feature["geometry"]),
    )


def load_montreal_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Montreal data using batched inserts."""
    import csv

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, ward, streetname, site, botanical_name, common_name,
        original_common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326))
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
    botanical_name = row["Essence_latin"]
    source_common_name = f"{row['Essence_fr']} ({row['ESSENCE_ANG']})"
    common_name, original_common_name = common_name_values(source_common_name, botanical_name)
    return (
        source,
        row["EMP_NO"],
        f"{row['ARROND_NOM']}",
        row["LOCALISATION"],
        row["Emplacement"],
        botanical_name,
        common_name,
        original_common_name,
        dbh,
        longitude,
        latitude,
    )


def load_calgary_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Calgary data using batched inserts."""
    import csv

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, structid, common_name, original_common_name, botanical_name,
        dbh_trunk, address, streetname, site, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
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
    common_name, original_common_name = common_name_values(row.get("COMMON_NAME"), botanical_name)
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
        common_name,
        original_common_name,
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
        source, objectid, common_name, original_common_name, botanical_name, address,
        dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
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
    common_name, original_common_name = common_name_values(
        properties.get("COM_NAME"), properties.get("LATIN_NAME")
    )
    return (
        source,
        properties.get("ASSET_ID"),
        common_name,
        original_common_name,
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
        botanical_name, common_name, original_common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
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
    common_name, original_common_name = common_name_values(
        properties.get("spp_com"), botanical_name
    )
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
        original_common_name,
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
        botanical_name, common_name, original_common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
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
    common_name, original_common_name = common_name_values(
        properties.get("COMMONNAME"), botanical_name
    )
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
        original_common_name,
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
        botanical_name, common_name, original_common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
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
    common_name, original_common_name = common_name_values(common_name, botanical_name)

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
        original_common_name,
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
        botanical_name, common_name, original_common_name, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
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
    botanical_name = properties.get("BOTANICAL")
    common_name, original_common_name = common_name_values(properties.get("COMMON"), botanical_name)

    return (
        source,
        properties.get("OBJECTID"),
        address,
        streetname,
        site,
        ward,
        botanical_name,
        common_name,
        original_common_name,
        json.dumps(geometry),
    )


def load_mississauga_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Mississauga data and insert it into the database."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, structid, address, site, ward,
        botanical_name, common_name, original_common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = mississauga_row_tuple(feature)
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Mississauga features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def mississauga_row_tuple(feature):
    """Build one Mississauga insert row."""
    source = "Mississauga City-Owned Tree Inventory"
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

    diameter = properties.get("DIAM")
    dbh_trunk = None
    if diameter not in (None, ""):
        try:
            dbh_trunk = round(float(diameter))
        except (TypeError, ValueError):
            dbh_trunk = None

    site_parts = [
        clean_text(properties.get("LOC")),
        clean_text(properties.get("SPACETYPE")),
        clean_text(properties.get("SERVSTAT")),
    ]
    site = " | ".join(part for part in site_parts if part) or None
    common_name = clean_text(properties.get("BOTDESC")) or clean_text(properties.get("BOTNAME"))
    if common_name:
        common_name = common_name.title()
    common_name, original_common_name = common_name_values(common_name)

    return (
        source,
        properties.get("OBJECTID"),
        clean_text(properties.get("UNITID")),
        None,
        site,
        clean_text(properties.get("ZAREA")),
        None,
        common_name,
        original_common_name,
        dbh_trunk,
        json.dumps(geometry),
    )


def load_san_francisco_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load San Francisco data using a CSV file."""
    import csv

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, address, site, ward, botanical_name, common_name,
        original_common_name, dbh_trunk, tree_position_number, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    ST_Multi(ST_SetSRID(ST_Point(%s, %s), 4326)))
    """

    rows = []
    with open(filename, "r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for idx, row in enumerate(reader, start=1):
            row_tuple = san_francisco_row_tuple(row)
            if row_tuple is None:
                continue
            rows.append(row_tuple)
            if len(rows) >= batch_size:
                _flush_batch(cursor, sql_query, rows, template, batch_size)
            if idx % PROGRESS_INTERVAL == 0:
                print(f"Processed {idx} San Francisco rows...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def san_francisco_row_tuple(row):
    """Build one San Francisco insert row."""
    source = "San Francisco Street Tree Inventory"
    properties = {k.lower(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}

    objectid = properties.get("treeid") or properties.get("tree_id")
    if objectid in (None, ""):
        return

    try:
        objectid = int(float(objectid))
    except (TypeError, ValueError):
        return

    def parse_float(value):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    dbh = parse_float(properties.get("dbh"))
    dbh_trunk = None if dbh is None else round(dbh)

    tree_position = parse_float(properties.get("siteorder"))
    if tree_position is None:
        tree_position = None
    else:
        tree_position = int(tree_position)

    longitude = parse_float(properties.get("longitude"))
    latitude = parse_float(properties.get("latitude"))
    if longitude is None or latitude is None:
        return

    species = properties.get("qspecies")
    common_name, original_common_name = common_name_values(species, species)

    return (
        source,
        objectid,
        properties.get("qaddress"),
        properties.get("qsiteinfo"),
        properties.get("qcaretaker"),
        species,
        common_name,
        original_common_name,
        dbh_trunk,
        tree_position,
        longitude,
        latitude,
    )


def load_madison_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Madison Wisconsin tree inventory GeoJSON."""
    with open(filename, "r") as file:
        data = json.load(file)

    sql_query = """
    INSERT INTO street_trees (
        source, objectid, site, ward, botanical_name, common_name,
        original_common_name, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = madison_row_tuple(feature)
        if row is None:
            continue
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Madison features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def madison_row_tuple(feature):
    """Build one Madison insert row."""
    source = "Madison Urban Forestry Street Trees"
    properties = feature["properties"]
    geometry = feature["geometry"]

    site = properties.get("site_id")
    if site in (None, ""):
        site = None

    dbh_raw = properties.get("DIAMETER")
    dbh_trunk = None
    if dbh_raw not in (None, ""):
        try:
            dbh_trunk = round(float(dbh_raw))
        except (TypeError, ValueError):
            dbh_trunk = None
    common_name, original_common_name = common_name_values(
        properties.get("SPP_COM"), properties.get("SPP_BOT")
    )

    return (
        source,
        properties.get("OBJECTID"),
        str(site) if site is not None else None,
        properties.get("STATUS"),
        properties.get("SPP_BOT"),
        common_name,
        original_common_name,
        dbh_trunk,
        point_to_multipoint_json(geometry),
    )


def load_geneva_data(cursor, filename, batch_size=DEFAULT_BATCH_SIZE):
    """Load Geneva SITG tree inventory from ArcGIS JSON or GeoJSON."""
    with open(filename, "r") as file:
        data = json.load(file)

    first_feature = next(iter(data.get("features", [])), None)
    if first_feature and "attributes" in first_feature:
        load_geneva_arcgis_json(cursor, data, batch_size)
    else:
        load_geneva_geojson(cursor, data, batch_size)


def load_geneva_geojson(cursor, data, batch_size):
    """Load Geneva GeoJSON features with WGS84 coordinates."""
    sql_query = """
    INSERT INTO street_trees (
        source, objectid, structid, address, site, ward, botanical_name, common_name,
        original_common_name, species_id, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s,
    (SELECT id FROM species WHERE species_key = %s), %s,
    ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = geneva_geojson_row_tuple(feature)
        if row is None:
            continue
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Geneva features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def load_geneva_arcgis_json(cursor, data, batch_size):
    """Load Geneva ArcGIS JSON features with LV95 coordinates."""
    sql_query = """
    INSERT INTO street_trees (
        source, objectid, structid, address, site, ward, botanical_name, common_name,
        original_common_name, species_id, dbh_trunk, geom
    ) VALUES %s
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    template = """
    (%s, %s, %s, %s, %s, %s, %s, %s, %s,
    (SELECT id FROM species WHERE species_key = %s), %s,
    ST_Multi(ST_Transform(ST_SetSRID(ST_Point(%s, %s), 2056), 4326)))
    """

    rows = []
    for idx, feature in enumerate(data["features"], start=1):
        row = geneva_arcgis_json_row_tuple(feature)
        if row is None:
            continue
        rows.append(row)
        if len(rows) >= batch_size:
            _flush_batch(cursor, sql_query, rows, template, batch_size)
        if idx % PROGRESS_INTERVAL == 0:
            print(f"Processed {idx} Geneva features...")

    _flush_batch(cursor, sql_query, rows, template, batch_size)


def geneva_geojson_row_tuple(feature):
    """Build one Geneva row from FeatureServer GeoJSON."""
    properties = feature["properties"]
    shared = geneva_shared_values(properties)
    if shared is None:
        return
    return (*shared, point_to_multipoint_json(feature["geometry"]))


def geneva_arcgis_json_row_tuple(feature):
    """Build one Geneva row from FeatureServer ArcGIS JSON."""
    properties = feature["attributes"]
    shared = geneva_shared_values(properties)
    geometry = feature.get("geometry") or {}
    x_coord = geometry.get("x")
    y_coord = geometry.get("y")
    if shared is None or x_coord is None or y_coord is None:
        return
    return (*shared, x_coord, y_coord)


def geneva_shared_values(properties):
    """Map Geneva attributes into the shared street_trees columns."""

    def prop(name):
        if name in properties:
            return properties.get(name)
        return properties.get(name.upper())

    objectid = parse_int(prop("id_arbre"))
    if objectid is None:
        objectid = parse_int(prop("objectid"))
    if objectid is None:
        return

    status = clean_text(prop("statut"))
    tree_class = clean_text(prop("classe"))
    site = " | ".join(part for part in [tree_class, status] if part) or None
    commune = clean_text(prop("commune"))
    postal_code = clean_text(prop("no_postal"))
    address = " ".join(part for part in [postal_code, commune] if part) or None
    botanical_name = clean_text(prop("nom_latin"))
    common_name, original_common_name, species_key = resolved_species_values(
        clean_text(prop("nom_commun")) or clean_text(prop("nom_com_re")),
        botanical_name,
        "Geneva Cantonal Tree Inventory",
    )

    return (
        "Geneva Cantonal Tree Inventory",
        objectid,
        clean_text(prop("globalid")),
        address,
        site,
        commune,
        botanical_name,
        common_name,
        original_common_name,
        species_key,
        parse_geneva_diameter_cm(prop("diam_1m"), prop("circonference")),
    )


def clean_text(value):
    """Return stripped text or None for empty values."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def common_name_values(source_common_name, botanical_name=None):
    """Return display and source common names for storage."""
    display_name, original_common_name, _species_key = resolved_species_values(
        source_common_name, botanical_name
    )
    return display_name, original_common_name


def resolved_species_values(source_common_name, botanical_name=None, source=None):
    """Return display name, source name, and catalog key when a species is known."""
    original_common_name = clean_text(source_common_name)
    resolution = resolve_species(source, botanical_name, original_common_name)
    if resolution:
        return resolution["display_common_name"], original_common_name, resolution["species_key"]
    return standardize_common_name(original_common_name), original_common_name, None


def standardize_common_name(source_common_name, botanical_name=None):
    """Format source species text as an English Canadian display name."""
    common_name = clean_text(source_common_name)
    if common_name is None:
        return None

    parenthesized_name = english_name_from_parentheses(common_name)
    if parenthesized_name:
        common_name = parenthesized_name

    common_name = common_name.replace("Gray", "Grey").replace("gray", "grey")
    common_name = " ".join(common_name.split())
    return title_common_name(common_name)


def resolve_species(source, botanical_name=None, source_common_name=None):
    """Resolve source species text to a curated catalog species, if known."""
    catalog = load_species_catalog()

    for candidate in botanical_name_candidates(botanical_name):
        species_key = catalog["botanical_aliases"].get(candidate)
        if species_key:
            return catalog["species_by_key"][species_key]

    common_key = normalize_species_text(source_common_name)
    if common_key:
        source_key = clean_text(source) or ""
        for lookup_key in ((source_key, common_key), ("", common_key)):
            species_key = catalog["common_aliases"].get(lookup_key)
            if species_key:
                return catalog["species_by_key"][species_key]
    return None


def load_species_catalog():
    """Load the checked-in species catalog seed files into lookup maps."""
    global _SPECIES_CATALOG_CACHE
    if _SPECIES_CATALOG_CACHE is not None:
        return _SPECIES_CATALOG_CACHE

    species_rows = read_seed_csv(SPECIES_CATALOG_FILE)
    alias_rows = read_seed_csv(SPECIES_ALIASES_FILE)
    species_by_key = {}
    botanical_aliases = {}
    common_aliases = {}

    for row in species_rows:
        species_key = row["species_key"]
        species_by_key[species_key] = row
        botanical_aliases[normalize_species_text(row["canonical_botanical_name"])] = species_key

    for row in alias_rows:
        species_key = row["species_key"]
        if species_key not in species_by_key:
            raise ValueError(f"Unknown species_key in alias seed: {species_key}")
        alias_key = normalize_species_text(row["alias"])
        if row["name_kind"] == "botanical":
            botanical_aliases[alias_key] = species_key
        elif row["name_kind"] == "common":
            common_aliases[(row["source"], alias_key)] = species_key
        else:
            raise ValueError(f"Unknown name_kind in alias seed: {row['name_kind']}")

    _SPECIES_CATALOG_CACHE = {
        "species_rows": species_rows,
        "alias_rows": alias_rows,
        "species_by_key": species_by_key,
        "botanical_aliases": botanical_aliases,
        "common_aliases": common_aliases,
    }
    return _SPECIES_CATALOG_CACHE


def read_seed_csv(path):
    """Read a species seed CSV with stripped field values."""
    with open(path, newline="", encoding="utf-8") as file:
        return [
            {key: clean_text(value) or "" for key, value in row.items()}
            for row in csv.DictReader(file)
        ]


def botanical_name_candidates(value):
    """Return increasingly broad botanical lookup keys."""
    normalized = normalize_species_text(value)
    if not normalized:
        return []

    candidates = [normalized]
    without_rank = re.split(r"\s+(subsp|ssp|var|f)\.?\s+", normalized, maxsplit=1)[0]
    if without_rank and without_rank not in candidates:
        candidates.append(without_rank)
    without_cultivar = re.sub(r"\s+'[^']+'", "", normalized).strip()
    if without_cultivar and without_cultivar not in candidates:
        candidates.append(without_cultivar)
    return candidates


def normalize_species_text(value):
    """Normalize species lookup text without changing its meaning."""
    text = clean_text(value)
    if text is None:
        return ""
    text = text.replace("×", " x ")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def common_name_key(value):
    """Normalize common-name text for exact lookup."""
    return " ".join(clean_text(value).casefold().split())


def botanical_name_key(value):
    """Normalize botanical-name text for exact lookup."""
    if value is None:
        return None
    return " ".join(str(value).casefold().replace("×", "x").split())


def english_name_from_parentheses(value):
    """Use parenthesized English names from bilingual source values when present."""
    text = clean_text(value)
    if not text or "(" not in text or not text.endswith(")"):
        return None
    _, parenthesized = text.rsplit("(", 1)
    candidate = parenthesized[:-1].strip()
    if not candidate or "," in candidate:
        return None
    if all(ord(char) < 128 for char in candidate):
        return candidate
    return None


def title_common_name(value):
    """Title-case a common name without damaging apostrophe cultivars."""
    titled_words = []
    for word in value.split():
        titled_words.append("-".join(title_word(part) for part in word.split("-")))
    return " ".join(titled_words)


def title_word(value):
    """Title-case one word segment."""
    if not value:
        return value
    prefix = ""
    suffix = ""
    while value and not value[0].isalnum():
        prefix += value[0]
        value = value[1:]
    while value and not value[-1].isalnum():
        suffix = value[-1] + suffix
        value = value[:-1]
    if not value:
        return prefix + suffix
    return f"{prefix}{value[0].upper()}{value[1:].lower()}{suffix}"


def parse_int(value):
    """Parse numeric IDs from integer-like source values."""
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def parse_geneva_diameter_cm(diameter_value, circumference_value=None):
    """Parse Geneva trunk diameter as centimeters, falling back from circumference."""
    diameter_cm = parse_float(diameter_value)
    if diameter_cm is not None:
        return round(diameter_cm)

    circumference_cm = parse_float(circumference_value)
    if circumference_cm is None:
        return None
    return round(circumference_cm / math.pi)


def parse_float(value):
    """Parse a numeric source value as float."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    parser = argparse.ArgumentParser(description="Tree Data Import and Enrichment CLI")
    parser.add_argument("city", choices=CITY_HANDLERS.keys(), help="City to process")
    parser.add_argument(
        "--file",
        help=(
            "Path to the data file. If omitted, the loader uses the newest file under "
            "data/raw/<city>/<YYYY-MM-DD>/."
        ),
    )
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
    if not filename:
        filename = str(latest_archived_dataset(city))
        print(f"Resolved latest archived dataset: {filename}")

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
        ensure_species_tables(cursor)
        seed_species_catalog(cursor)
        ensure_street_tree_species_columns(cursor)

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
