# TE-010: Repeatable Enrichment Jobs

## Status

todo

## Priority

P1

## Depends On

- TE-002
- TE-004
- TE-005
- TE-006
- TE-007

## Summary

Add repeatable enrichment job commands/scripts with idempotent upsert behavior.

The first practical use case is refreshing Wikipedia-backed species profiles, but the job structure should also support future enrichment sources such as benefits, risk signals, media, and local stats.

## Product Goal

TreeSeek should be able to safely refresh enrichment data without manual database edits and without creating duplicate records.

## Initial Command

Add or confirm a command similar to:

```sh
make enrich-species-profiles
```

Optional dry-run mode:

```sh
make enrich-species-profiles DRY_RUN=1
```

or:

```sh
python scripts/enrich_species_profiles.py --dry-run
```

## Requirements

- Job can be run repeatedly.
- Running the same job twice does not duplicate data.
- Job updates existing records when source data changes.
- Job records or preserves provenance fields.
- Job supports dry-run mode.
- Job logs summary counts.
- Job fails clearly when source data cannot be fetched or parsed.

## Provenance Fields

Each enrichment write should include or preserve:

```text
source_system
source_url
retrieved_at
method_version
confidence
license
attribution
```

## Suggested Job Output

Example successful run:

```text
Species profile enrichment complete.
Checked: 120 species
Created: 15 profiles
Updated: 8 profiles
Unchanged: 97 profiles
Skipped: 0
Errors: 0
```

Example dry run:

```text
DRY RUN: no database changes written.
Checked: 120 species
Would create: 15 profiles
Would update: 8 profiles
Would leave unchanged: 97 profiles
Would skip: 0
Errors: 0
```

## Acceptance Criteria

- Enrichment job is idempotent.
- Dry-run mode exists.
- Job has useful console output.
- Job writes or preserves provenance fields.
- Job handles missing Wikipedia URL gracefully.
- Job handles failed fetches gracefully.
- Job is documented.
- Tests or smoke checks cover upsert behavior.
- Running the job twice produces no duplicate enrichment rows.

## Future Notes

This may later be generalized into an enrichment job runner with per-source methods, for example:

```sh
make enrich-profiles
make enrich-risk
make enrich-benefits
make enrich-media
```

Do not over-engineer this until at least two enrichment types exist.
