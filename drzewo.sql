CREATE DATABASE drzewo ;

\c drzewo

CREATE EXTENSION IF NOT EXISTS postgis;


CREATE TABLE street_trees (
    source TEXT NOT NULL,
    city_id INTEGER,
    objectid INTEGER NOT NULL,
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
    geom GEOMETRY(MultiPoint, 4326) NOT NULL -- WGS 84
);


ALTER TABLE street_trees ADD CONSTRAINT unique_source_objectid UNIQUE (source, objectid);

CREATE INDEX idx_street_trees_geom_gist ON street_trees USING GIST (geom);

CREATE TABLE import_runs (
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

CREATE INDEX idx_import_runs_city_finished_at
    ON import_runs (city, finished_at DESC);
