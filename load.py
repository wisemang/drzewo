#!/usr/bin/env python3

from os import path, environ
import psycopg2
import json


# Database connection parameters
db_params = {
    "database": environ.get('DRZEWO_DB', 'drzewo'),
    "user": environ.get('DRZEWO_DB_USER', 'greg'),
    "password": environ.get('DRZEWO_DB_PW', None),
    "host": environ.get('DRZEWO_DB_HOST', 'localhost'),
    "port": environ.get('DRZEWO_DB_PORT', '5432')
}


def insert_toronto_street_tree_data(cursor, feature):
    properties = feature['properties']
    geometry = json.dumps(feature['geometry'])  # Convert geometry to JSON string

    sql = """
    INSERT INTO street_trees (
        source, city_id, objectid, structid, address, streetname,
        crossstreet1, crossstreet2, suffix, unit_number, tree_position_number,
        site, ward, botanical_name, common_name, dbh_trunk, geom
    ) VALUES (
        %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
    )
    """
    cursor.execute(sql, (
        'Toronto Open Data Street Trees',
        properties.get('city_id'),
        properties.get('OBJECTID'),
        properties.get('STRUCTID'),
        properties.get('ADDRESS'),
        properties.get('STREETNAME'),
        properties.get('CROSSSTREET1'),
        properties.get('CROSSSTREET2'),
        properties.get('SUFFIX'),
        properties.get('UNIT_NUMBER'),
        properties.get('TREE_POSITION_NUMBER'),
        properties.get('SITE'),
        properties.get('WARD'),
        properties.get('BOTANICAL_NAME'),
        properties.get('COMMON_NAME'),
        properties.get('DBH_TRUNK'),
        geometry
    ))


def insert_ottawa_tree_inventory_data(cursor, feature):
    properties = feature['properties']
    geometry = feature['geometry']
    
    # Convert Point to MultiPoint if necessary
    if geometry['type'] == 'Point':
        geometry['type'] = 'MultiPoint'
        geometry['coordinates'] = [geometry['coordinates']]
    geometry_json = json.dumps(geometry)  # Convert geometry to JSON string

    sql = """
    INSERT INTO street_trees (
        source, objectid, address, streetname,
        botanical_name, common_name, dbh_trunk, geom
    ) VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)
    )
    """
    cursor.execute(sql, (
        'Ottawa Open Data Tree Inventory',
        properties.get('OBJECTID'),
        properties.get('ADDNUM'),
        properties.get('ADDSTR'),
        properties.get('SPECIES'),    # Assuming 'SPECIES' maps to 'botanical_name'
        properties.get('SPECIES'),    # Assuming 'SPECIES' also maps to 'common_name'
        properties.get('DBH'),
        geometry_json
    ))


def load_and_insert_toronto_street_tree_data(filename):
    with open(filename, 'r') as file:
        data = json.load(file)
        
    conn = None
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        # Loop through each feature in the GeoJSON file
        for feature in data['features']:
            insert_toronto_street_tree_data(cursor, feature)
        
        conn.commit()  # Commit the transaction
        print("Toronto data inserted successfully.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


def load_and_insert_ottawa_tree_inventory_data(filename):
    with open(filename, 'r') as file:
        data = json.load(file)
        
    conn = None
    try:
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()
        
        # Loop through each feature in the GeoJSON file
        for feature in data['features']:
            insert_ottawa_tree_inventory_data(cursor, feature)
        
        conn.commit()  # Commit the transaction
        print("Ottawa data inserted successfully.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()


load_and_insert_toronto_street_tree_data(path.expanduser('~/dev/drzewo/data/Street Tree Data.geojson'))
load_and_insert_ottawa_tree_inventory_data(path.expanduser('~/dev/drzewo/data/Tree_Inventory.geojson'))
