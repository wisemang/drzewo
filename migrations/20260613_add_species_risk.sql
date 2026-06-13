CREATE TABLE IF NOT EXISTS species_risk (
    id BIGSERIAL PRIMARY KEY,
    species_id BIGINT NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    risk_type TEXT NOT NULL,
    status TEXT NOT NULL,
    region TEXT NOT NULL,
    region_type TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ,
    observed_at TIMESTAMPTZ,
    method_version TEXT NOT NULL,
    confidence TEXT NOT NULL DEFAULT 'unreviewed',
    license_name TEXT,
    license_url TEXT,
    attribution TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (retrieved_at IS NOT NULL OR observed_at IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_species_risk_species_id
    ON species_risk (species_id);

CREATE TABLE IF NOT EXISTS species_risk_observation (
    id BIGSERIAL PRIMARY KEY,
    species_risk_id BIGINT REFERENCES species_risk(id) ON DELETE CASCADE,
    species_id BIGINT NOT NULL REFERENCES species(id) ON DELETE CASCADE,
    risk_type TEXT NOT NULL,
    region TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    observation_date DATE,
    source_system TEXT NOT NULL,
    source_record_id TEXT,
    source_url TEXT,
    confidence TEXT NOT NULL DEFAULT 'unreviewed',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (latitude IS NULL AND longitude IS NULL)
        OR (latitude IS NOT NULL AND longitude IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_species_risk_observation_species_id
    ON species_risk_observation (species_id);
