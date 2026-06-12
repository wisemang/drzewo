# TE-006: Species Risk Model

## Status

todo

## Priority

P1

## Depends On

- TE-001
- TE-003

## Summary

Add `species_risk` and `species_risk_observation` support for native, introduced, invasive, pest, and pathogen signals.

The initial orientation may be EDDMapS-style invasive/risk data, but the model should be region-aware and flexible enough to support multiple sources.

## Product Goal

TreeSeek should eventually help users understand whether a species has local ecological or management concerns, such as invasive status, pest/pathogen relevance, or introduced/native status.

## Design Principle

Risk and native/invasive status are region-specific.

The same species may be native in one region, introduced in another, and invasive or watchlisted elsewhere. The API and UI must not present region-specific claims as global species facts.

## Possible Risk Types

```text
native_status
introduced_status
naturalized_status
invasive_status
watchlist_status
pest_host
pathogen_host
pest_observation
pathogen_observation
management_concern
```

## Possible Status Values

```text
native
introduced
naturalized
invasive
potentially_invasive
watchlist
present
reported
not_reported
unknown
```

These are candidates, not necessarily final enum values.

## Data Requirements

Risk records should include:

```text
species_id
risk_type
status
region
region_type
source_system
source_url
retrieved_at
observed_at
method_version
confidence
license
attribution
notes
```

Risk observations may include:

```text
species_id
risk_type
region
latitude
longitude
observation_date
source_system
source_record_id
source_url
confidence
notes
```

Only include coordinates if allowed by source licensing and privacy rules.

## Example API Section

```json
{
  "risk": {
    "available": true,
    "region": "Ontario",
    "items": [
      {
        "risk_type": "native_status",
        "status": "native",
        "confidence": "medium",
        "source_system": "example_source",
        "source_url": "https://example.org/source",
        "label": "Native in Ontario"
      }
    ]
  }
}
```

## UI Requirements

The UI should show concise badges or labels, for example:

```text
Native in Ontario
```

or:

```text
Invasive concern in Ontario
```

Avoid vague global claims such as:

```text
Invasive species
```

unless the region is explicit or the source itself defines the claim globally.

## Non-Goals

- Do not implement full EDDMapS ingestion until source licensing and use constraints are confirmed.
- Do not show risk badges without source and region.
- Do not treat native/invasive status as a universal species-level field.
- Do not block the initial Wikipedia species profile panel on this work.

## Acceptance Criteria

- Species risk flags are queryable by region, risk type, source, confidence, and freshness.
- Region-specific claims include region metadata.
- Source attribution and freshness fields are present.
- Missing risk data is handled gracefully.
- Tests cover null-safe behavior.
- Tests cover prevention of region-specific claims being surfaced as global facts.
