#!/usr/bin/env python3

import argparse
import json
from os import environ

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


def load_toronto_data(cursor, filename):
    """Load Toronto data and insert it into the database."""
    with open(filename, "r") as file:
        data = json.load(file)

    for feature in data["features"]:
        insert_toronto_data(cursor, feature)


def insert_toronto_data(cursor, feature):
    """
    Insert Toronto tree data into the database.
    """
    # Extract fields
    source = "Toronto Open Data Street Trees"
    properties = feature['properties']
    geometry = json.dumps(feature['geometry'])  # Convert geometry to JSON string

    objectid = properties.get('OBJECTID')
    structid = properties.get('STRUCTID')
    address = properties.get('ADDRESS')
    streetname = properties.get('STREETNAME')
    crossstreet1 = properties.get('CROSSSTREET1')
    crossstreet2 = properties.get('CROSSSTREET2')
    suffix = properties.get('SUFFIX')
    unit_number = properties.get('UNIT_NUMBER')
    tree_position_number = properties.get('TREE_POSITION_NUMBER')
    site = properties.get('SITE')
    ward = properties.get('WARD')
    botanical_name = properties.get('BOTANICAL_NAME')
    common_name = properties.get('COMMON_NAME')
    dbh_trunk = properties.get('DBH_TRUNK')

    # Create SQL query
    sql_query = """
    INSERT INTO street_trees (
        source, objectid, structid, address, streetname, crossstreet1, crossstreet2, suffix,
        unit_number, tree_position_number, site, ward, botanical_name, common_name, dbh_trunk, geom
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
    )
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    cursor.execute(sql_query, (
        source,
        objectid,
        structid,
        address,
        streetname,
        crossstreet1,
        crossstreet2,
        suffix,
        unit_number,
        tree_position_number,
        site,
        ward,
        botanical_name,
        common_name,
        dbh_trunk,
        geometry
    ))

def load_ottawa_data(cursor, filename):
    """Load Ottawa data and insert it into the database."""
    with open(filename, "r") as file:
        data = json.load(file)

    for feature in data["features"]:
        insert_ottawa_data(cursor, feature)


def insert_ottawa_data(cursor, feature):
    """
    Insert Ottawa tree data into the database.
    """
    source = "Ottawa Open Data Tree Inventory"
    properties = feature['properties']
    geometry = feature['geometry']

    # Convert Point to MultiPoint if necessary
    if geometry['type'] == 'Point':
        geometry['type'] = 'MultiPoint'
        geometry['coordinates'] = [geometry['coordinates']]
    geometry_json = json.dumps(geometry)

    objectid = properties.get('OBJECTID')
    address = properties.get('ADDNUM')
    streetname = properties.get('ADDSTR')
    botanical_name = properties.get('SPECIES')  # Assuming 'SPECIES' maps to botanical_name
    common_name = properties.get('SPECIES')  # Same as botanical_name for simplicity
    dbh_trunk = properties.get('DBH')

    # Create SQL query
    sql_query = """
    INSERT INTO street_trees (
        source, objectid, address, streetname, botanical_name, common_name, dbh_trunk, geom
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
    )
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    cursor.execute(sql_query, (
        source,
        objectid,
        address,
        streetname,
        botanical_name,
        common_name,
        dbh_trunk,
        geometry_json
    ))

def load_montreal_data(cursor, filename):
    """
    Load Montreal data from a CSV file and insert it into the database.
    """
    import csv

    with open(filename, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            insert_montreal_data(cursor, row)


def insert_montreal_data(cursor, row):
    """
    Insert Montreal tree data into the database.
    """
    # Extract fields
    # Columns include:
    # INV_TYPE, EMP_NO, ARROND, ARROND_NOM, Rue, COTE, No_civique, Emplacement,
    # Coord_X, Coord_Y, SIGLE, Essence_latin, Essence_fr, ESSENCE_ANG, DHP,
    # Date_releve, Date_plantation, LOCALISATION, CODE_PARC, NOM_PARC, Longitude, Latitude
    source = "Montreal Open Data Tree Inventory"
    objectid = row['EMP_NO']
    ward = f"{row['ARROND_NOM']}"
    streetname = row['LOCALISATION']
    site = row['Emplacement'] # Trottoir, Fond de Trottoir, Parterre Gazonné, ...
    botanical_name = row['Essence_latin']
    common_name = f"{row['Essence_fr']} ({row['ESSENCE_ANG']})"
    if row['DHP']:
        dbh = round(float(row['DHP']))
    else:
        dbh = None
    longitude = row['Longitude']
    latitude = row['Latitude']

    # Skip rows without valid coordinates
    if not longitude or not latitude:
        return

    # Create SQL query
    sql_query = """
    INSERT INTO street_trees (
        source, objectid, ward, streetname, site, botanical_name, common_name, dbh_trunk, geom
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_Point(%s, %s), 4326)
    )
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    cursor.execute(sql_query, (
        source,
        objectid,
        ward,
        streetname,
        site,
        botanical_name,
        common_name,
        dbh,
        longitude,
        latitude
    ))


def load_calgary_data(cursor, filename):
    """
    Load Calgary data from a CSV file and insert it into the database.
    """
    import csv

    with open(filename, 'r') as file:
        reader = csv.DictReader(file)  # Adjust if a specific delimiter is needed
        for row in reader:
            insert_calgary_data(cursor, row)

def insert_calgary_data(cursor, row):
    """
    Insert Calgary tree data into the database.
    """
    # Extract fields
    objectid = row['TREE_ASSET_CD']
    asset_type = row['ASSET_TYPE']
    asset_subtype = row['ASSET_SUBTYPE']
    common_name = row['COMMON_NAME']
    botanical_name = f"{row['GENUS']} {row['SPECIES']} {row['CULTIVAR']}".strip()
    dbh_trunk = row['DBH_CM']
    address = row['LOCATION_DETAIL']
    streetname = row['COMM_CODE']
    date_added = row['ACTIVE_DT']
    point_wkt = row['POINT']

    # Parse WKT into PostGIS geometry
    sql_query = """
    INSERT INTO street_trees (
        source, objectid, asset_type, asset_subtype, common_name, botanical_name,
        dbh_trunk, address, streetname, date_added, geom
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326)
    )
    ON CONFLICT (objectid) DO NOTHING;
    """
    cursor.execute(sql_query, (
        "Calgary Open Data Tree Inventory",
        objectid,
        asset_type,
        asset_subtype,
        common_name,
        botanical_name,
        dbh_trunk,
        address,
        streetname,
        date_added,
        point_wkt
    ))


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


def load_waterloo_data(cursor, filename):
    """Load Waterloo data and insert it into the database."""
    with open(filename, 'r') as file:
        data = json.load(file)

    for feature in data['features']:
        insert_waterloo_data(cursor, feature)

def insert_waterloo_data(cursor, feature):
    """Insert Waterloo tree data into the database."""
    source = "Waterloo Open Data Tree Inventory"
    properties = feature['properties']
    geometry = feature['geometry']

    objectid = properties.get('ASSET_ID')
    common_name = properties.get('COM_NAME')
    botanical_name = properties.get('LATIN_NAME')
    address = properties.get('ADDRESS')
    dbh_trunk = properties.get('DBH_CM')
    if dbh_trunk == 'null':
        dbh_trunk = None

    # Create SQL query
    sql_query = """
    INSERT INTO street_trees (
        source, objectid, common_name, botanical_name, address, dbh_trunk, geom
    ) VALUES (
        %s, %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
    )
    ON CONFLICT (source, objectid) DO NOTHING;
    """
    cursor.execute(sql_query, (
        source,
        objectid,
        common_name,
        botanical_name,
        address,
        dbh_trunk,
        json.dumps(geometry)
    ))


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
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Rows per batched INSERT for large imports (default: 1000)",
    )

    args = parser.parse_args()
    city = args.city
    filename = args.file
    apply_enrichments = args.enrich
    batch_size = max(1, args.batch_size)

    city_config = CITY_HANDLERS[city]

    conn = connect_db()
    try:
        cursor = conn.cursor()

        print(f"Loading data for {city}...")
        if city == "toronto":
            load_toronto_data(cursor, filename)
        elif city == "ottawa":
            load_ottawa_data(cursor, filename)
        elif city == "montreal":
            load_montreal_data(cursor, filename)
        elif city == "calgary":
            load_calgary_data(cursor, filename)
        elif city == "waterloo":
            load_waterloo_data(cursor, filename)
        elif city == "boston":
            load_boston_data(cursor, filename, batch_size=batch_size)
        elif city == "markham":
            load_markham_data(cursor, filename, batch_size=batch_size)
        elif city == "oakville":
            load_oakville_data(cursor, filename, batch_size=batch_size)
        elif city == "peterborough":
            load_peterborough_data(cursor, filename, batch_size=batch_size)

        if apply_enrichments:
            print(f"Applying enrichments for {city}...")
            enrich_data(cursor, city_config)

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
    finally:
        conn.close()


if __name__ == "__main__":
    main()
