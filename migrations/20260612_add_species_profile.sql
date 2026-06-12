CREATE TABLE IF NOT EXISTS species_profile (
    id BIGSERIAL PRIMARY KEY,
    species_id BIGINT NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    summary TEXT,
    taxonomy JSONB NOT NULL DEFAULT '{}'::jsonb,
    canonical_url TEXT,
    source_system TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NOT NULL,
    method_version TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'unreviewed',
    license_name TEXT,
    license_url TEXT,
    attribution TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (species_id, source_system)
);

CREATE INDEX IF NOT EXISTS idx_species_profile_species_id
    ON species_profile (species_id);
