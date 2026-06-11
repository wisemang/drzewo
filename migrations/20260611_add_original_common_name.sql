CREATE TABLE IF NOT EXISTS species (
    id BIGSERIAL PRIMARY KEY,
    species_key TEXT NOT NULL UNIQUE,
    canonical_botanical_name TEXT NOT NULL UNIQUE,
    display_common_name TEXT NOT NULL,
    wikipedia_url TEXT
);

CREATE TABLE IF NOT EXISTS species_name_alias (
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

ALTER TABLE street_trees
    ADD COLUMN IF NOT EXISTS original_common_name TEXT;

ALTER TABLE street_trees
    ADD COLUMN IF NOT EXISTS species_id BIGINT REFERENCES species(id);

CREATE INDEX IF NOT EXISTS idx_street_trees_species_id
    ON street_trees (species_id);

UPDATE street_trees
SET original_common_name = common_name
WHERE original_common_name IS NULL
  AND common_name IS NOT NULL;

UPDATE street_trees
SET common_name = 'Grey Birch'
WHERE lower(original_common_name) IN ('birch, grey', 'birch, gray');

UPDATE street_trees
SET common_name = 'English Oak'
WHERE source = 'Geneva Cantonal Tree Inventory'
  AND lower(botanical_name) LIKE 'quercus robur%';
