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
| TE-005 | P1 | todo | TE-001, TE-003 | Add benefit model support for species-level qualitative benefits and tree-level calculated estimates. | Benefit model stores metric type, scope (`species` vs `tree_instance`), estimate fields, units, assumptions, method version, confidence, and provenance. |
| TE-006 | P1 | todo | TE-001, TE-003 | Add `species_risk` + `species_risk_observation` for native/introduced/invasive/pest/pathogen signals, with EDDMapS-oriented risk support. | Species risk flags queryable by region, risk type, source, confidence, and freshness; UI/API must not present region-specific claims as global facts. |
| TE-007 | P2 | todo | TE-001, TE-003 | Add `species_media` for public-domain or compatible-license imagery plus attribution payload. | At least one image path with license + credit metadata can be returned for a species. |
| TE-008A | P1 | todo | TE-004 | Add species profile API response contract for current profile data. | `/species/<species_id>/profile` follows `docs/backlog/treeseek-enrichment-specs/TE-008A-species-profile-api.md`: common name, botanical name, sectioned summary, source URL, license, attribution, provenance, and null-safe missing-data behavior; documented and tested. |
| TE-008B | P1 | todo | TE-005, TE-006, TE-007, TE-011, TE-015 | Expand species profile API with optional enrichment sections. | API supports optional `benefits`, `risk`, `media`, `local_stats`, and section-level provenance without breaking existing clients. |
| TE-009A | P1 | todo | TE-008A | Frontend: species profile panel launched from tree popup. | Popup includes an “About [species]” action; panel renders common name, botanical name, summary, Wikipedia link, and attribution; existing map/table workflow remains unchanged. |
| TE-009B | P1 | todo | TE-008B | Frontend: enrichment sections in species panel. | Panel renders optional benefits, risk badges, media, local stats, and source/provenance sections with graceful missing-data fallbacks. |
| TE-010 | P1 | todo | TE-002, TE-004, TE-005, TE-006, TE-007 | Add repeatable enrichment job commands/scripts (idempotent upsert behavior). | Running job twice does not duplicate data; dry-run mode exists for review. |
| TE-011 | P1 | todo | TE-008A | Add API/loader tests for “fact vs estimate vs risk signal” semantics and null-safe behavior. | Tests validate labeling, confidence handling, and missing-data fallbacks. |
| TE-012 | P2 | todo | TE-010 | Add enrichment observability (`enrichment_runs` audit table + summary script). | Each enrichment run logs status, counts, and timing; failures captured with error text. |
| TE-013 | P2 | todo | TE-009B | Optional imagery moderation/caching policy (fallback image, stale-link handling). | Broken/missing images degrade gracefully; attribution still visible. |
| TE-014 | P0 | done | none | Decide legal/licensing constraints and attribution requirements for all external sources before production sync. | Decision log added in this file with approved source list and usage constraints. |
| TE-015 | P1 | todo | TE-001, TE-008A | Add local TreeSeek-derived species stats to the species profile API and panel. | API can return same-species mapped-record counts, radius/context metadata, nearby DBH stats when location is supplied, cities/datasets where the species appears, and clear copy that these are TreeSeek mapped-record stats. |

## Suggested Execution Order

1. `TE-014` licensing and attribution guardrails
2. `TE-001` schema foundation
3. `TE-002` normalization in loader
4. `TE-003` provenance model
5. `TE-004` profile enrichment
6. `TE-005` benefits enrichment
7. `TE-006` risk enrichment
8. `TE-008A` current profile API contract
9. `TE-009A` current profile frontend panel
10. `TE-011` expanded semantics/null-safe tests
11. `TE-015` local TreeSeek species stats
12. `TE-008B` future enrichment API sections
13. `TE-009B` future enrichment frontend sections
14. `TE-010` idempotent enrichment jobs
15. `TE-007`, `TE-012`, `TE-013` lower-priority follow-through

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
- Consequences: Profile enrichment can be run and refreshed independently. `TE-008A` tracks the current profile contract, while `TE-008B` remains open for later benefits/risk/media/local-stats expansion.
