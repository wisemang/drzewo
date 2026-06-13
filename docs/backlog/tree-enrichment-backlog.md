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
| TE-005 | P1 | done | TE-001, TE-003 | Add benefit model support for species-level qualitative benefits and tree-level calculated estimates. | `species_benefit` stores metric type, scope, estimate fields, units, assumptions, method version, confidence, and provenance; `/species/<species_id>/profile` returns valid species-scope benefit items when present and otherwise keeps `benefits: null`. |
| TE-006 | P1 | done | TE-001, TE-003 | Add `species_risk` + `species_risk_observation` for native/introduced/invasive/pest/pathogen signals, with EDDMapS-oriented risk support. | Risk tables store region-aware status, provenance, confidence, and freshness metadata; `/species/<species_id>/profile` returns only valid regional risk items and otherwise keeps `risk: null`. |
| TE-007 | P2 | todo | TE-001, TE-003 | Add `species_media` for public-domain or compatible-license imagery plus attribution payload. | At least one image path with license + credit metadata can be returned for a species. |
| TE-008A | P1 | done | TE-004 | Add species profile API response contract for current profile data. | `/species/<species_id>/profile` follows `docs/backlog/treeseek-enrichment-specs/TE-008A-species-profile-api.md`: common name, botanical name, sectioned summary, source URL, license, attribution, provenance, and null-safe missing-data behavior; documented and tested. |
| TE-008B | P1 | done | TE-005, TE-006, TE-007, TE-011 | Expand species profile API with remaining optional enrichment sections. | `/species/<species_id>/profile` explicitly normalizes optional sections so unavailable or untrustworthy `benefits`, `risk`, and `media` remain `null`; valid benefits/risk sections use the shared `{ "available": true, "items": [...] }` shape; `media` stays `null` until `TE-007` lands. |
| TE-009A | P1 | done | TE-008A | Frontend: species profile panel launched from tree popup. | Popup includes an “About [species]” action; panel renders common name, botanical name, summary, Wikipedia link, and attribution; existing map/table workflow remains unchanged. |
| TE-009B | P1 | todo | TE-008B | Frontend: remaining enrichment sections in species panel. | Panel renders optional benefits, risk badges, and media with graceful missing-data fallbacks while preserving the current summary, local stats, and provenance behavior. |
| TE-010 | P1 | done | TE-002, TE-004, TE-005, TE-006, TE-007 | Add repeatable enrichment job commands/scripts (idempotent upsert behavior). | Running job twice does not duplicate data; dry-run mode exists for review. |
| TE-011 | P1 | done | TE-008A | Add API/loader tests for “fact vs estimate vs risk signal” semantics and null-safe behavior. | Tests validate the current source-derived summary contract, unavailable benefit/risk/media sections, confidence handling, and missing-data fallbacks. |
| TE-012 | P2 | todo | TE-010 | Add enrichment observability (`enrichment_runs` audit table + summary script). | Each enrichment run logs status, counts, and timing; failures captured with error text. |
| TE-013 | P2 | todo | TE-009B | Optional imagery moderation/caching policy (fallback image, stale-link handling). | Broken/missing images degrade gracefully; attribution still visible. |
| TE-014 | P0 | done | none | Decide legal/licensing constraints and attribution requirements for all external sources before production sync. | Decision log added in this file with approved source list and usage constraints. |
| TE-015 | P1 | done | TE-001, TE-008A | Add local TreeSeek-derived species stats to the species profile API and panel. | API returns same-species mapped-record count, radius, and largest nearby DBH when explicit location context is supplied; the species panel renders those local stats when present. Broader aggregate stats such as cities/datasets remain future enhancement work. |

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
12. `TE-008B` future benefits/risk/media API sections
13. `TE-009B` future benefits/risk/media frontend sections
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
- Consequences: Profile enrichment can be run and refreshed independently. `TE-008A` tracks the current profile contract, while `TE-008B` remains open for later benefits/risk/media expansion.

### 2026-06-12 - Species API identity semantics
- Context: The profile API exposes both numeric `species_id` and human-readable `species_key`.
- Decision: Treat numeric `species_id` as the durable route/join identity. Treat `species_key` as a stable-but-migratable API/display convenience unless an explicit immutable-key policy is adopted later.
- Consequences: Future taxonomy, synonym, or normalization fixes should preserve `species_id` where possible, document any `species_key` changes, and avoid encouraging clients to treat `species_key` as the only durable identifier.

### 2026-06-13 - Species benefits model boundary
- Context: `TE-005` needs a durable benefits model now, but the current profile panel and API should not start implying per-tree modeled estimates without tree-specific context or caveats.
- Decision: Store benefits in a dedicated `species_benefit` table that can represent both qualitative species notes and future tree-instance estimates via `scope`, estimate fields, assumptions, provenance, and optional tree identifiers. Expose only valid `scope='species'` items through `/species/<species_id>/profile` for now; keep malformed or absent benefits as `null`.
- Consequences: The API gains a narrow, null-safe benefits section without expanding risk/media work or surfacing tree-instance model outputs in the species profile route. Future work can add enrichment jobs and tree-context endpoints on top of the same table.

### 2026-06-13 - Species risk model boundary
- Context: `TE-006` needs native/invasive/pest-pathogen support, but the species profile route must not flatten regional signals into global species facts or emit placeholder-safe claims.
- Decision: Store risk signals in `species_risk` plus optional `species_risk_observation`, with explicit region, region type, provenance, confidence, and freshness fields. Expose only well-formed `species_risk` rows through `/species/<species_id>/profile`; filter unknown, regionless, or undated rows so `risk` remains `null` when certainty is not supported.
- Consequences: The API can return concise, region-explicit risk items now while leaving richer ingestion, observation-driven endpoints, and frontend badge rendering for later slices.
