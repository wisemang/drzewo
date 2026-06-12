# Tree Enrichment Backlog

This file is the canonical tracker for species/tree enrichment work.

## Workflow

Use these status values only:

- `todo`: not started
- `in-progress`: actively being worked
- `blocked`: waiting on dependency/decision
- `done`: merged and validated

Update this file in the same commit as implementation changes.

## Priority Guide

- `P0`: foundation required for all downstream enrichment
- `P1`: high user value, can start after P0 foundation
- `P2`: nice-to-have or polish

## Backlog Items

| ID | Priority | Status | Depends On | Scope | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- |
| TE-001 | P0 | done | none | Add normalized species tables (`species`, `species_name_alias`) and `street_trees.species_id` linkage. | Migration applied; existing imports still work; species join path covered by tests. |
| TE-002 | P0 | done | TE-001 | Add deterministic species normalization in `tree_loader.py` (clean botanical/common names, synonym handling). | Loader assigns `species_id` consistently across cities; normalization tests added for edge cases. |
| TE-003 | P0 | done | TE-001 | Add source metadata model for enrichments (`source_system`, `source_url`, `retrieved_at`, `method_version`, `confidence`). | Enrichment tables include provenance fields; API can expose them. |
| TE-004 | P1 | done | TE-001, TE-003 | Add `species_profile` enrichment (Wikipedia-level summary + taxonomy basics + canonical links). | Profile record available for known species; API returns profile block with attribution URL. |
| TE-005 | P1 | todo | TE-001, TE-003 | Add `species_benefit_model` for ecological/environmental/economic estimates. | Carbon, pollution, stormwater, and economic estimate fields stored with assumption metadata. |
| TE-006 | P1 | todo | TE-001, TE-003 | Add `species_risk` + `species_risk_observation` for invasive/pest/pathogen signals (EDDMapS-oriented). | Species risk flags queryable by region and risk type; attribution and freshness fields present. |
| TE-007 | P2 | todo | TE-001, TE-003 | Add `species_media` for public-domain or compatible-license imagery plus attribution payload. | At least one image path with license + credit metadata can be returned for a species. |
| TE-008 | P1 | todo | TE-004, TE-005, TE-006 | Expand API response model (tree + profile + benefits + risk + provenance). | New endpoint or expanded payload documented and covered by tests. |
| TE-009 | P1 | todo | TE-008 | Frontend: species detail card/panel with profile, benefits summary, risk badges, and source links. | UI renders enrichment sections without breaking existing map/table workflow. |
| TE-010 | P1 | todo | TE-002, TE-004, TE-005, TE-006, TE-007 | Add repeatable enrichment job commands/scripts (idempotent upsert behavior). | Running job twice does not duplicate data; dry-run mode exists for review. |
| TE-011 | P1 | todo | TE-008 | Add API/loader tests for “fact vs estimate vs risk signal” semantics and null-safe behavior. | Tests validate labeling, confidence handling, and missing-data fallbacks. |
| TE-012 | P2 | todo | TE-010 | Add enrichment observability (`enrichment_runs` audit table + summary script). | Each enrichment run logs status, counts, and timing; failures captured with error text. |
| TE-013 | P2 | todo | TE-009 | Optional imagery moderation/caching policy (fallback image, stale-link handling). | Broken/missing images degrade gracefully; attribution still visible. |
| TE-014 | P0 | done | none | Decide legal/licensing constraints and attribution requirements for all external sources before production sync. | Decision log added in this file with approved source list and usage constraints. |

## Suggested Execution Order

1. `TE-014` licensing and attribution guardrails
2. `TE-001` schema foundation
3. `TE-002` normalization in loader
4. `TE-003` provenance model
5. `TE-004` profile enrichment
6. `TE-005` benefits enrichment
7. `TE-006` risk enrichment
8. `TE-008` API expansion
9. `TE-009` frontend integration
10. `TE-010` idempotent enrichment jobs
11. `TE-011` expanded tests
12. `TE-007`, `TE-012`, `TE-013` lower-priority follow-through

## Decisions Log

Add dated entries when a source, method, or modeling assumption changes.

Template:

```md
### YYYY-MM-DD - Decision title
- Context:
- Decision:
- Consequences:
```

### 2026-06-12 - Wikipedia profile provenance
- Context: Species names and catalog links have been standardized; Wikipedia URLs now exist in the seed catalog, but richer profiles need attribution and freshness metadata.
- Decision: Treat Wikipedia as the first approved profile source for short species summaries, canonical article URLs, and basic taxonomy-style facts only. Store source provenance on each profile record using `source_system`, `source_url`, `retrieved_at`, `method_version`, and `confidence`, with license and attribution fields populated when data is fetched.
- Consequences: Wikipedia links remain seed catalog metadata until an enrichment job creates `species_profile` rows. Any API/frontend surface must show source attribution and avoid presenting imported prose as locally authored content.

### 2026-06-12 - Wikipedia profile endpoint
- Context: The profile provenance table exists; the next user-visible step is making seeded Wikipedia URLs produce retrievable species profiles.
- Decision: Add `make enrich-species-profiles` as the first Wikipedia profile population path and expose profiles through `/species/<species_id>/profile`, rather than expanding `/nearest` before the full enriched tree response design.
- Consequences: Profile enrichment can be run and refreshed independently. `TE-008` remains open for a later combined tree/profile/benefit/risk response.
