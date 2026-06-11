CREATE DATABASE drzewo ;

\c drzewo

CREATE EXTENSION IF NOT EXISTS postgis;


CREATE TABLE species (
    id BIGSERIAL PRIMARY KEY,
    species_key TEXT NOT NULL UNIQUE,
    canonical_botanical_name TEXT NOT NULL UNIQUE,
    display_common_name TEXT NOT NULL,
    wikipedia_url TEXT
);

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
    original_common_name TEXT,
    species_id BIGINT REFERENCES species(id),
    dbh_trunk INTEGER,
    geom GEOMETRY(MultiPoint, 4326) NOT NULL -- WGS 84
);


ALTER TABLE street_trees ADD CONSTRAINT unique_source_objectid UNIQUE (source, objectid);

CREATE INDEX idx_street_trees_geom_gist ON street_trees USING GIST (geom);
CREATE INDEX idx_street_trees_species_id ON street_trees (species_id);

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
