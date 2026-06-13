CREATE TABLE IF NOT EXISTS species_benefit (
    id BIGSERIAL PRIMARY KEY,
    species_id BIGINT NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    tree_source TEXT,
    tree_objectid INTEGER,
    metric_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    label TEXT,
    text TEXT,
    value DOUBLE PRECISION,
    unit TEXT,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    currency TEXT,
    region TEXT,
    method_version TEXT NOT NULL,
    assumptions TEXT,
    confidence TEXT NOT NULL DEFAULT 'unreviewed',
    source_system TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ,
    calculated_at TIMESTAMPTZ,
    license_name TEXT,
    license_url TEXT,
    attribution TEXT,
    caveat TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (scope IN ('species', 'species_region', 'city', 'location', 'tree_instance')),
    CHECK (retrieved_at IS NOT NULL OR calculated_at IS NOT NULL),
    CHECK (
        scope <> 'tree_instance'
        OR (tree_source IS NOT NULL AND tree_objectid IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_species_benefit_species_id
    ON species_benefit (species_id);
