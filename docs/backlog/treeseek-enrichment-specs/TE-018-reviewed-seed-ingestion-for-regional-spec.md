TE-018 — Reviewed Seed Ingestion for Regional Species Risk/Status Signals

Status

Todo

Priority

P0

Depends on

* TE-006 — Risk model support
* TE-010 — Repeatable enrichment job commands/scripts
* TE-016 — First benefits/risk data source strategy

Summary

Implement the first production-safe risk/status data population path.

This item adds make enrich-risk for reviewed, source-backed, region-aware species risk/status records. The first ingestion should include VASCAN Ontario regional origin/status records and a narrow CFIA emerald ash borer overlay for ash species.

Risk frontend rendering remains out of scope unless separately feature-gated.

Goals

* Add a repeatable risk enrichment command.
* Import Ontario regional status records from reviewed VASCAN-derived seed data.
* Import a narrow CFIA emerald ash borer concern overlay for Fraxinus species.
* Require complete provenance for every inserted row.
* Keep missing/unmatched species as risk: null.
* Avoid implying missing risk data means safe.
* Avoid broad invasive claims without explicit jurisdiction/source.

Non-goals

* Do not ingest EDDMapS occurrence data.
* Do not infer absence/safety from missing observations.
* Do not classify species as invasive unless directly supported by the cited jurisdiction/source.
* Do not render risk in the frontend as part of this item.
* Do not add OIPC/SERO/CABI text ingestion.
* Do not add live scraping.

Source strategy

Source 1: VASCAN

Use for:

* regional_origin_status
* Ontario regional status only
* region: CA-ON
* scope: species

Allowed status values should be mapped from the source vocabulary, for example:

* native
* introduced
* ephemeral
* extirpated
* doubtful
* absent
* excluded

Important semantic constraint:

* VASCAN regional status is not a risk score.
* Native does not mean safe.
* Introduced does not mean invasive.

Source 2: CFIA emerald ash borer

Use for:

* regulated_pest_concern
* Fraxinus species or genus-level ash host records
* scope: genus or species, depending on existing schema support
* region: Canada or narrower region if the source/seed supports it

Required note constraint:

* Must not imply that an individual ash tree is infested.

Acceptable note pattern:

Ash species are associated with CFIA emerald ash borer regulation. This does not mean this individual tree is infested.

Seed file

Add a reviewed seed file, for example:

* data/enrichment/risk_seed.jsonl

Example VASCAN-style row:

{
  "species_id": "acer_saccharum",
  "scientific_name": "Acer saccharum",
  "risk_type": "regional_origin_status",
  "metric_type": "categorical_status",
  "status": "native",
  "note": "Listed as native in Ontario by VASCAN.",
  "scope": "species",
  "region": "CA-ON",
  "source_id": "vascan",
  "source_title": "VASCAN: Database of Vascular Plants of Canada",
  "source_url": "https://data.canadensys.net/ipt/resource.do?r=vascan",
  "attribution": "VASCAN / Canadensys",
  "license": "CC0",
  "confidence": "high",
  "retrieved_date": "2026-06-15",
  "observed_effective_date": null,
  "method_version": "risk_seed_vascan_cfia_v1"
}

Example CFIA-style row:

{
  "species_id": "fraxinus_pennsylvanica",
  "scientific_name": "Fraxinus pennsylvanica",
  "risk_type": "regulated_pest_concern",
  "metric_type": "qualitative_caution",
  "status": "regulated_pest_host",
  "note": "Ash species are associated with CFIA emerald ash borer regulation. This does not mean this individual tree is infested.",
  "scope": "genus",
  "region": "Canada",
  "source_id": "cfia_eab",
  "source_title": "CFIA: Emerald ash borer regulated areas and items",
  "source_url": "https://inspection.canada.ca/en/plant-health/invasive-pests-and-plants/directives/forest-products/03-08/regulated-areas",
  "attribution": "Canadian Food Inspection Agency / Government of Canada",
  "license": "Open Government Licence - Canada, where applicable",
  "confidence": "high",
  "retrieved_date": "2026-06-15",
  "observed_effective_date": null,
  "method_version": "risk_seed_vascan_cfia_v1"
}

Command

Add:

make enrich-risk

Recommended options if existing job style supports them:

make enrich-risk DRY_RUN=1
make enrich-risk SEED=data/enrichment/risk_seed.jsonl

Behavior:

* Validate seed file.
* Reject rows missing required provenance.
* Reject unsupported risk types.
* Reject missing region.
* Resolve species_id against existing species table.
* Upsert idempotently.
* Produce count summary:
    * rows read
    * rows inserted
    * rows updated
    * rows skipped
    * rows rejected
    * species touched

Required validation

Reject rows where:

* species_id does not resolve.
* risk_type is unsupported.
* metric_type is missing.
* both status and note are empty.
* region is empty.
* source_url is empty.
* source_title is empty.
* attribution is empty.
* license is empty.
* confidence is missing or outside allowed values.
* row uses “safe”, “no risk”, or equivalent missing-data-as-safety language.
* row labels a species invasive/restricted/prohibited without an explicit cited jurisdiction/source.
* row uses placeholder text such as Unknown, N/A, or No data available.

API behavior

After ingestion:

* /species/<species_id>/profile returns sections.risk only for species with valid imported records.
* Species with no valid risk records still return risk: null.
* Risk uses the existing TE-008B { "available": true, "items": [...] } shape.
* Frontend risk rendering remains disabled unless a separate item enables it.

Tests

Add tests for:

* valid VASCAN-style regional status row imports successfully
* valid CFIA EAB row imports successfully
* rerunning import is idempotent
* missing provenance rejects row
* missing region rejects row
* unresolved species rejects row or skips without placeholder
* unsupported risk_type rejects row
* “safe” wording rejects row
* invasive/restricted claim without statutory source rejects row
* unmatched species profile keeps risk: null
* imported species profile exposes valid sections.risk
* dry-run does not write rows

Initial pilot

Seed reviewed records for a small pilot set:

* Acer saccharum — VASCAN regional status
* Acer rubrum — VASCAN regional status
* Acer platanoides — VASCAN regional status only; do not add invasive/statutory claim yet
* Fraxinus pennsylvanica — VASCAN status + CFIA EAB overlay
* Fraxinus americana — VASCAN status + CFIA EAB overlay
* Quercus rubra — VASCAN status; oak wilt overlay deferred until reviewed
* Tilia cordata — VASCAN regional status if present
* Gleditsia triacanthos — VASCAN regional status if present
* Celtis occidentalis — VASCAN regional status if present
* Ginkgo biloba — VASCAN regional status if present

Acceptance criteria

* make enrich-risk exists.
* Dry-run mode exists if consistent with existing TE-010 job conventions.
* Job imports reviewed local seed records.
* Job is idempotent.
* Every imported row has complete provenance.
* Every imported row has region metadata.
* Invalid rows are rejected or skipped with explicit counts.
* Missing/unmatched species remain risk: null.
* No missing-risk-as-safe wording is stored or exposed.
* No broad invasive/statutory claims are inserted without direct cited source support.
* /species/<species_id>/profile returns valid risk records for seeded species.
* Tests cover success, rejection, idempotency, and null behavior.
