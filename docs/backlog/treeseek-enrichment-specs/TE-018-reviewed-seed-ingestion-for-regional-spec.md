TE-018 - Reviewed Seed Ingestion for Regional Species Risk/Status Signals

Status

Done

Priority

P0

Depends on

- TE-006 - Risk model support
- TE-010 - Repeatable enrichment job commands/scripts
- TE-016 - First benefits/risk data source strategy

Summary

Implement the first production-safe risk/status seed ingestion path.

This item adds `make enrich-risk` for reviewed, source-backed, region-aware
species risk/status records. The first slice imports Ontario regional status
records from VASCAN and a narrow CFIA emerald ash borer pest-host overlay for
pilot `Fraxinus` species.

Risk frontend rendering remains out of scope.

Goals

- Add a repeatable risk enrichment command.
- Import reviewed Ontario regional status records from VASCAN-derived seed data.
- Import a narrow CFIA emerald ash borer overlay for ash host species.
- Require complete provenance for every inserted row.
- Keep missing or unmatched species as `risk: null`.
- Avoid implying missing risk data means safe.
- Avoid broad invasive claims without direct source support.

Non-goals

- Do not ingest EDDMapS occurrence data.
- Do not infer safety from missing observations.
- Do not add OIPC, SERO, or CABI ingestion.
- Do not enable frontend risk rendering.
- Do not add live scraping.

First-slice source mapping

Source 1: VASCAN / Database of Vascular Plants of Canada

Use only Ontario regional status:

- `region = CA-ON`
- `region_type = province`
- Ontario native records map to `risk_type = native_status`
- Ontario introduced records map to `risk_type = introduced_status`

Important semantic constraints:

- This is regional status, not a risk score.
- Native does not mean safe.
- Introduced does not mean invasive.
- Ambiguous statuses remain deferred from this slice.

Source 2: CFIA emerald ash borer

Use only a narrow ash host overlay for pilot `Fraxinus` species:

- `risk_type = pest_host`
- `region = CA`
- `region_type = country`

Required note constraint:

- Notes must not imply that the individual mapped tree is infested.

Approved first-slice seed shape

Add:

- `data/enrichment/risk_seed.jsonl`

Seed rows resolve species by `species_key` and/or `scientific_name`. Seed
authors do not need numeric `species_id` values.

Example VASCAN row:

```json
{
  "species_key": "acer_rubrum",
  "scientific_name": "Acer rubrum",
  "common_name": "Red Maple",
  "risk_type": "native_status",
  "status": "native",
  "note": "VASCAN lists this species as native in Ontario.",
  "region": "CA-ON",
  "region_type": "province",
  "source_system": "vascan",
  "source_title": "VASCAN: Database of Vascular Plants of Canada",
  "source_url": "https://data.canadensys.net/vascan/taxon/9212?lang=en",
  "license_name": "Creative Commons Attribution-ShareAlike 3.0 Unported (CC BY-SA 3.0)",
  "license_url": "https://creativecommons.org/licenses/by-sa/3.0/",
  "attribution": "VASCAN / Canadensys",
  "retrieved_at": "2026-06-15",
  "observed_at": null,
  "method_version": "risk_seed_vascan_cfia_v1",
  "confidence": "high",
  "signal_key": "acer_rubrum_native_status_ca_on_vascan"
}
```

Example CFIA row:

```json
{
  "species_key": "fraxinus_americana",
  "scientific_name": "Fraxinus americana",
  "common_name": "White Ash",
  "risk_type": "pest_host",
  "status": "reported",
  "note": "Ash species are associated with CFIA emerald ash borer host and regulatory concern. This does not mean this individual tree is infested.",
  "region": "CA",
  "region_type": "country",
  "source_system": "cfia_eab",
  "source_title": "CFIA: Emerald ash borer",
  "source_url": "https://inspection.canada.ca/en/plant-health/invasive-pests-and-plants/insects/emerald-ash-borer",
  "license_name": "Open Government Licence - Canada",
  "license_url": "https://open.canada.ca/en/open-government-licence-canada",
  "attribution": "Canadian Food Inspection Agency / Government of Canada",
  "retrieved_at": "2026-06-15",
  "observed_at": null,
  "method_version": "risk_seed_vascan_cfia_v1",
  "confidence": "high",
  "signal_key": "fraxinus_americana_pest_host_ca_cfia"
}
```

Importer behavior

Add:

```sh
make enrich-risk
```

Supported options:

```sh
make enrich-risk DRY_RUN=1
make enrich-risk SEED=data/enrichment/risk_seed.jsonl
```

Behavior:

- Validate the reviewed JSONL seed file.
- Reject rows missing required provenance.
- Reject unsupported `risk_type` values.
- Reject rows missing `region` or `region_type`.
- Resolve species identity against the existing species catalog.
- Do not create new species records.
- Upsert idempotently using the resolved species and approved source key.
- Produce a count summary:
  - rows read
  - rows inserted
  - rows updated
  - rows skipped
  - rows rejected
  - species touched

Approved first-slice `risk_type` values

- `native_status`
- `introduced_status`
- `pest_host`
- `management_concern` only if a reviewed row later needs it and has direct
  source support

Current implementation rules

- `native_status` rows must use `status = native`
- `introduced_status` rows must use `status = introduced`
- `pest_host` rows must use `status = present` or `status = reported`
- `management_concern` rows must use `status = present` or `status = reported`

Required validation

Reject rows where:

- `species_key` and `scientific_name` both fail to resolve
- `risk_type` is not approved
- `status` is missing or unsupported for the chosen `risk_type`
- `note` is missing
- `region` is missing
- `region_type` is missing
- `source_system` is missing
- `source_title` is missing
- `source_url` is missing
- `license_name` is missing
- `license_url` is missing
- `attribution` is missing
- `retrieved_at` is missing
- `method_version` is missing
- `confidence` is missing or outside `high | medium | low`
- note or status uses placeholder text such as `Unknown`, `N/A`, or
  `No data available`
- note uses safety wording such as `safe`, `no risk`, `not risky`, or
  `risk-free`
- note makes a broad invasive/statutory claim such as `invasive`,
  `restricted`, or `prohibited`
- duplicate rows share the same species/risk/source/region identity

Suggested upsert identity

- resolved numeric `species_id`
- `risk_type`
- `region`
- `region_type`
- `source_system`
- `source_url`
- `method_version`

`signal_key` is allowed as a seed-only reviewer field and is not persisted.

API behavior

After ingestion:

- `/species/<species_id>/profile` returns `sections.risk` only for species with
  valid imported records
- malformed, missing, or unmatched optional sections still return `risk: null`
- the API keeps the existing `{"available": true, "items": [...]}` shape
- frontend risk rendering remains disabled

Initial pilot rows reviewed for this slice

- `Acer saccharum` - VASCAN Ontario native status
- `Acer rubrum` - VASCAN Ontario native status
- `Acer platanoides` - VASCAN Ontario introduced status only
- `Fraxinus pennsylvanica` - VASCAN Ontario native status + CFIA EAB pest-host
  overlay
- `Fraxinus americana` - VASCAN Ontario native status + CFIA EAB pest-host
  overlay
- `Quercus rubra` - VASCAN Ontario native status only
- `Celtis occidentalis` - VASCAN Ontario native status
- `Tilia cordata` - VASCAN Ontario introduced status
- `Gleditsia triacanthos` - VASCAN Ontario native status

Deferred from the reviewed seed because it was not present or unambiguous in
the source pass:

- `Ginkgo biloba`

Acceptance criteria

- `make enrich-risk` exists
- dry-run mode exists
- reviewed local seed records import through the current schema
- reruns are idempotent
- every imported row has complete provenance
- every imported row has region metadata
- invalid rows are rejected with explicit counts
- missing or unmatched species remain `risk: null`
- no missing-risk-as-safe wording is stored or exposed
- no broad invasive/statutory claims are inserted without direct source support
- `/species/<species_id>/profile` continues to expose only valid risk rows
- tests cover success, rejection, idempotency, and dry-run behavior
