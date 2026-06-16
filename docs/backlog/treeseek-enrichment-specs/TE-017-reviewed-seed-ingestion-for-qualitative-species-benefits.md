TE-017 — Reviewed Seed Ingestion for Qualitative Species Benefits

Status

done

Priority

P0

Depends on

* TE-005 — Benefit model support
* TE-010 — Repeatable enrichment job commands/scripts
* TE-016 — First benefits/risk data source strategy

Summary

Implement the first production-safe benefit data population path.

This item adds make enrich-benefits for reviewed, source-backed, species-level qualitative benefit notes. The job imports local seed/review records into the existing species_benefit model using idempotent upsert behavior.

This is intentionally a seed ingestion job first, not a live scraper or broad automated claim extractor.

Goals

* Add a repeatable benefits enrichment command.
* Import reviewed qualitative benefit notes for a small pilot species set.
* Require complete provenance for every inserted row.
* Keep missing/unmatched species as benefits: null.
* Preserve existing API contract and frontend behavior.
* Avoid numeric/modelled/tree-instance estimates.

Non-goals

* Do not add i-Tree calculations.
* Do not add tree-instance benefit estimates.
* Do not scrape arbitrary web pages.
* Do not generate ecological claims with an LLM.
* Do not alter the benefits frontend beyond what is already supported.
* Do not populate risk data in this item.

Source strategy

Approved first source:

* USDA NRCS PLANTS / Plant Guides

Usage rules:

* Use short, reviewed, paraphrased notes only.
* Do not bulk-copy long source prose.
* Store source title, source URL, attribution, licence, confidence, retrieved date, and method version.
* Confidence should usually be medium unless a note is directly source-supported and broadly applicable.

Seed file

Add a reviewed seed file, for example:

* data/enrichment/benefits_seed.jsonl

Each row should use the existing model/API vocabulary where possible.

Example shape:

{
  "species_key": "acer_rubrum",
  "scientific_name": "Acer rubrum",
  "common_name": "Red maple",
  "metric_type": "pollinator_support",
  "note": "Can provide early-season floral resources for some pollinating insects.",
  "scope": "species",
  "region": null,
  "source_system": "usda_plants",
  "source_title": "USDA NRCS PLANTS Database / Plant Guide",
  "source_url": "https://plants.sc.egov.usda.gov/",
  "attribution": "U.S. Department of Agriculture, Natural Resources Conservation Service",
  "license_name": "Public domain; USDA attribution requested",
  "license_url": "https://www.usda.gov/about-usda/policies-and-links",
  "confidence": "medium",
  "retrieved_at": "2026-06-15",
  "observed_at": null,
  "method_version": "benefits_seed_usda_plants_v1",
  "claim_key": "acer_rubrum_pollinator_support_001"
}

If a source registry already exists, source metadata may be referenced by `source_system`, but the imported database rows/API output must still expose enough provenance to satisfy TE-003/TE-008B behavior.

Command

Add:

make enrich-benefits

Recommended options if the existing job style supports them:

make enrich-benefits DRY_RUN=1
make enrich-benefits SEED=data/enrichment/benefits_seed.jsonl

Behavior:

* Validate the seed file.
* Reject rows missing required provenance.
* Reject rows with unsupported metric_type.
* Reject rows with unsupported scope.
* Reject rows containing numeric/tree-instance estimates.
* Resolve species identity against the existing species table.
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

* species identity does not resolve.
* note is empty.
* source_url is empty.
* source_title is empty.
* attribution is empty.
* license_name is empty.
* confidence is missing or outside allowed values.
* metric_type is not one of the approved first-slice values:
    * wildlife_food
    * wildlife_habitat
    * pollinator_support
    * shade_or_amenity
    * site_rehabilitation
    * cultural_or_human_use
* scope is not species.
* row includes estimate/unit/tree-instance fields.
* row uses placeholder text such as Unknown, N/A, or No data available.

API behavior

After ingestion:

* /species/<species_id>/profile returns sections.benefits only for species with valid imported records.
* Species with no valid records still return benefits: null.
* Benefits use the existing TE-008B { "available": true, "items": [...] } shape.
* Risk remains unchanged.

Tests

Add tests for:

* valid benefit seed row imports successfully
* rerunning import is idempotent
* missing provenance rejects row
* unresolved species rejects row or skips without placeholder
* unsupported metric_type rejects row
* numeric/modelled estimate fields reject row
* unmatched species profile keeps benefits: null
* imported species profile exposes valid sections.benefits
* malformed optional benefits still normalize to null
* dry-run does not write rows

Future consideration: a later schema/API cleanup may split benefit records into `metric_type=qualitative_note` plus a first-class `benefit_type` or `category` field. That is intentionally deferred from this seed-ingestion slice to avoid combining data population with model redesign.

Initial pilot

Seed a small number of reviewed rows for 5–10 common species before expanding.

Suggested initial species:

* Acer saccharum
* Acer rubrum
* Fraxinus pennsylvanica
* Quercus rubra
* Tilia cordata
* Gleditsia triacanthos
* Celtis occidentalis
* Ginkgo biloba

Acceptance criteria

* make enrich-benefits exists.
* Dry-run mode exists if consistent with existing TE-010 job conventions.
* Job imports reviewed local seed records.
* Job is idempotent.
* Every imported row has complete provenance.
* Invalid rows are rejected or skipped with explicit counts.
* No numeric/modelled/tree-instance benefit estimates are created.
* Missing/unmatched species remain benefits: null.
* /species/<species_id>/profile returns valid benefits for seeded species.
* Tests cover success, rejection, idempotency, and null behavior.
