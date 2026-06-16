TE-016 — First Benefits/Risk Data Source Strategy

Status

Todo

Priority

P0

Depends on

* TE-003 — Source metadata model
* TE-005 — Benefit model support
* TE-006 — Risk model support
* TE-014 — Legal/licensing constraints

Summary

Define the first concrete, production-safe data strategy for populating TreeSeek species benefits and risk data.

The existing schema/API supports optional sections.benefits and sections.risk, but production data is not yet populated. This item chooses narrow first sources and usage rules so enrichment jobs can be implemented without inventing ecological claims, copying proprietary text, implying that missing risk data means a species is safe, or requiring unplanned schema/API changes.

This item is a source/methodology and vocabulary-alignment decision. It does not perform ingestion.

Goals

* Approve a narrow first-source strategy for species-level qualitative benefits.
* Approve a narrow first-source strategy for region-aware risk/status signals.
* Align first-slice source concepts to the existing DB/API vocabulary.
* Define allowed first-slice enums/values for seed files and import validation.
* Define source/provenance field requirements using current schema names.
* Define seed identity and idempotent upsert keys.
* Define a small pilot species target list.
* Preserve current null-safe optional-section behavior.

Non-goals

* Do not implement enrichment jobs.
* Do not render risk in the frontend.
* Do not add new DB enum concepts unless separately required.
* Do not add tree-instance numeric/modelled benefit estimates.
* Do not ingest EDDMapS occurrence data.
* Do not ingest proprietary encyclopedia, arboretum, nursery, blog, or field-guide prose.
* Do not treat native/introduced status as a planting recommendation or risk rating.

⸻

Approved first sources

Benefits source

Approved first source:

* USDA NRCS PLANTS / Plant Guides

Permitted use:

* Species-level qualitative benefit notes only.
* Short paraphrased notes derived from source-supported claims.
* Human-reviewed seed records only for the first implementation slice.
* Store complete source provenance for every row.

Deferred benefits methodology:

* i-Tree or other numeric ecosystem-service estimates.
* Tree-instance benefits based on DBH/canopy/location.
* LLM-generated benefit claims without source-backed review.
* Bulk scraped prose from arboretum, nursery, municipal, or encyclopedia sources.

Risk/status source 1

Approved first source:

* VASCAN / Database of Vascular Plants of Canada

Permitted use:

* Ontario regional species status only.
* Store as existing risk model values, not as a new generic regional_origin_status enum.
* Region: CA-ON
* Region type: province

Important semantic constraint:

* VASCAN status is a regional origin/status signal, not a risk score.
* Native does not mean safe.
* Introduced does not mean invasive.

Risk/status source 2

Approved narrow overlay:

* CFIA emerald ash borer source material

Permitted use:

* Narrow pest-host or management-concern overlay for Fraxinus species.
* Must not imply that an individual tree is infested.
* Region: CA
* Region type: country
* Use narrower region only if directly supported by the reviewed source record.

Deferred risk sources/methods:

* Full EDDMapS ingestion.
* Broad invasive species claims without explicit jurisdiction/source.
* CABI or other restricted/proprietary text.
* OIPC/SERO management guidance as direct bulk-ingested text.
* Ontario statutory invasive labels unless verified directly against the regulation/list being cited.

⸻

Current-schema vocabulary alignment

This first slice must use existing schema/API vocabulary from api.py and drzewo.sql.

Do not introduce new persisted enum-like values such as:

* regional_origin_status
* regulated_pest_concern

unless the implementation first updates the schema/API contract deliberately.

Benefits vocabulary

The current benefits model exposes `metric_type` and does not currently enforce a fixed database enum.

For the first seed-ingestion slice, do not add a new persisted `benefit_type` field. Use `species_benefit.metric_type` as the canonical category field for qualitative species-level benefit notes.

Approved first-slice `metric_type` values:

* `wildlife_food`
* `wildlife_habitat`
* `pollinator_support`
* `shade_or_amenity`
* `site_rehabilitation`
* `cultural_or_human_use`

These values are intentionally more specific than older planning examples such as `ecological_value_note` or `wildlife_value_note`, because they are easier to review, test, and render as grouped qualitative notes.

Existing test/example values such as `shade_cooling` should remain supported where already present, but TE-017 reviewed seed imports should use only the approved first-slice values above unless this document is updated.

All first-slice benefit records must be:

* species-scope
* qualitative note records
* non-numeric
* non-estimate
* non-tree-instance

Do not persist a seed-only `benefit_type` unless it is used only for reviewer readability and is mapped deterministically to `metric_type` before database import.

Risk vocabulary

The current risk model exposes risk_type values including:

* native_status
* introduced_status
* pest_host
* management_concern

For the first slice, source concepts map as follows:

Source concept  Persisted risk_type Notes
VASCAN status = native in Ontario   native_status   Region must be CA-ON; region_type=province.
VASCAN status = introduced in Ontario   introduced_status   Region must be CA-ON; introduced does not mean invasive.
VASCAN status = ephemeral/extirpated/doubtful/absent/excluded   defer unless current schema has a safe representation   Do not force these into native/introduced categories.
CFIA emerald ash borer host signal for ash  pest_host   Preferred first mapping for Fraxinus/EAB. Must not imply individual tree infestation.
CFIA or reviewed source management caution  management_concern  Use only when the source supports a management-level caution rather than host status.

Do not persist a generic regional_origin_status risk type in this slice.

Do not persist invasive/statutory claims unless the source directly supports that exact jurisdictional claim.

⸻

Required source/provenance field names

Use current schema/API field names.

Every approved seed/import row must resolve or populate:

* source_system
* source_url
* source_title, if supported by current schema/API or seed validator
* license_name
* license_url
* attribution
* retrieved_at
* observed_at, if source provides an observation/effective date
* method_version
* confidence

If the current DB only stores a subset of these fields, the seed file may include the richer fields, but the importer must either persist them where supported or reject rows when required current-schema provenance is missing.

⸻

Seed identity

The database species_id is numeric.

Seed files should not require authors to know numeric IDs.

First-slice seed records should identify target species using one or more stable lookup fields:

* species_key, preferred if already available in the repo
* scientific_name
* optional common_name for review readability only

Importer behavior:

* Resolve seed identity to numeric species_id before insert/update.
* Reject or skip unresolved species with an explicit validation count.
* Do not create new species records as part of benefits/risk enrichment.
* Do not use string examples such as acer_rubrum as persisted species_id values.

Recommended seed identity shape:

{
  "species_key": "acer_rubrum",
  "scientific_name": "Acer rubrum",
  "common_name": "Red maple"
}

If species_key does not exist in the current repo, TE-017/TE-018 should use scientific_name as the seed lookup key and document the resolver behavior.

⸻

Idempotent upsert keys

TE-017 and TE-018 must implement deterministic upsert behavior.

Recommended first-pass natural keys:

Benefits

A benefit seed row is unique by:

* resolved numeric species_id
* metric_type
* scope
* region, nullable
* source_system
* source_url
* method_version

If two rows need the same species/metric/source but represent distinct notes, add a stable seed field such as claim_key.

Recommended benefits key:

species_id + metric_type + scope + region + source_system + source_url + method_version + claim_key

Risk

A risk seed row is unique by:

* resolved numeric species_id
* risk_type
* region
* region_type
* source_system
* source_url
* method_version

If multiple rows share the same source/risk/region for one species, add a stable seed field such as signal_key.

Recommended risk key:

species_id + risk_type + region + region_type + source_system + source_url + method_version + signal_key

Rerunning the same seed file must update the existing row, not duplicate it.

⸻

Confidence vocabulary

The reviewed seed importers must restrict confidence to:

* high
* medium
* low

Recommended first-slice use:

* high: direct structured source status or direct regulatory/host signal from an authoritative source.
* medium: direct species-level qualitative benefit note from a credible source, paraphrased for TreeSeek.
* low: allowed in schema only if already supported, but first production seeds should generally avoid publishing low-confidence rows.

Rows with missing or unsupported confidence values must be rejected.

⸻

Region and region_type rules

First-slice region values:

Source  Region  Region type
VASCAN Ontario status   CA-ON   province
CFIA emerald ash borer ash overlay  CA  country
USDA PLANTS benefits    North America, US, or null depending on existing schema constraints use existing nullable/region behavior

If the current schema expects a constrained region_type, use:

* province
* country
* continent
* source_scope
* unknown

Do not invent new region types without schema/API updates.

For benefits, if region metadata is not reliable or not supported, store region=null rather than overclaiming Ontario applicability.

⸻

Pilot species targets

Resolve these to actual repo species records before TE-017/TE-018 import.

Preferred seed lookup should be species_key if present, otherwise scientific_name.

Initial pilot list:

Scientific name Common name Purpose
Acer saccharum  Sugar maple native regional-status baseline
Acer rubrum Red maple   native regional-status baseline + benefit note candidate
Acer platanoides    Norway maple    introduced regional-status baseline; no statutory invasive claim yet
Fraxinus pennsylvanica  Green ash   VASCAN status + CFIA EAB pest-host overlay
Fraxinus americana  White ash   VASCAN status + CFIA EAB pest-host overlay
Quercus rubra   Northern red oak    native regional-status baseline
Tilia cordata   Littleleaf linden   introduced/common urban ornamental baseline
Gleditsia triacanthos   Honey locust    common urban species baseline
Celtis occidentalis Common hackberry    native regional-status baseline
Ginkgo biloba   Ginkgo  introduced/common urban ornamental baseline

Pilot labels describe test coverage only. They must not be rendered as user-facing risk classifications.

Avoid labels such as:

* safe
* unsafe
* extreme risk
* non-invasive
* recommended
* provincially restricted, unless directly verified from the cited statutory source

⸻

Wording rules

Benefit notes must use cautious species-level language:

Allowed patterns:

* “Can provide…”
* “May support…”
* “Is reported by [source] as…”
* “Is associated with…”

Avoid:

* “Provides major carbon benefits.”
* “Improves air quality.”
* “Is good for wildlife.”
* “Saves X litres of stormwater.”
* “Stores X kg of carbon.”

Risk/status notes must not imply safety from missing data.

Acceptable:

* “Listed as native in Ontario by VASCAN.”
* “Listed as introduced in Ontario by VASCAN.”
* “Ash species are associated with CFIA emerald ash borer host/regulatory concern. This does not mean this individual tree is infested.”

Avoid:

* “Safe”
* “No risk”
* “Not invasive”
* “Healthy”
* “Infested”
* “Recommended for planting”

⸻

Null behavior

If no approved source-backed record exists:

* sections.benefits remains null
* sections.risk remains null

Do not write placeholders such as:

* Unknown
* N/A
* No data available
* empty item arrays pretending to be populated records

Missing risk data must not be represented as safety.

⸻

Deliverables

* Add a source/methodology decision document under docs/backlog/treeseek-enrichment-specs/.
* Document approved first sources and usage constraints.
* Document deferred/rejected sources.
* Document canonical first-slice benefit metric_type values or mapping rules.
* Document canonical first-slice risk risk_type mappings.
* Document required provenance fields using current schema names.
* Document seed identity and species resolution behavior.
* Document idempotent upsert keys.
* Document confidence vocabulary.
* Document first-slice region and region_type rules.
* Document pilot species list.

⸻

Acceptance criteria

* Decision document exists and is linked from the backlog.
* USDA PLANTS is approved as first qualitative benefits source.
* VASCAN is approved as first Ontario regional status source.
* CFIA emerald ash borer is approved as a narrow ash pest-host overlay.
* EDDMapS full ingestion is explicitly deferred pending licensing/use review.
* Tree-instance numeric benefit estimates are explicitly deferred.
* First-slice benefit categories are mapped to current metric_type behavior.
* First-slice risk concepts are mapped to current risk_type values.
* Required provenance fields use current schema/API names including license_name, license_url, retrieved_at, and observed_at.
* region_type is defined for VASCAN and CFIA records.
* Seed identity does not require numeric species_id authoring.
* Idempotent upsert keys are documented.
* Confidence vocabulary is frozen to high, medium, and low.
* Null-safe missing-data behavior is explicitly preserved.
* Pilot species list is defined and ready for resolver implementation.
