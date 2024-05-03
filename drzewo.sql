CREATE DATABASE drzewo ;

\c drzewo

CREATE EXTENSION IF NOT EXISTS postgis;


CREATE TABLE street_trees (
    source TEXT,
    city_id INTEGER,
    objectid INTEGER,
    structid TEXT,
    address TEXT,
    streetname TEXT,
    crossstreet1 TEXT,
    crossstreet2 TEXT,
    suffix TEXT,
    unit_number TEXT,
    tree_position_number INTEGER,
    site TEXT,
    ward TEXT,
    botanical_name TEXT,
    common_name TEXT,
    dbh_trunk INTEGER,
    geom GEOMETRY(MultiPoint, 4326) -- WGS 84
);


