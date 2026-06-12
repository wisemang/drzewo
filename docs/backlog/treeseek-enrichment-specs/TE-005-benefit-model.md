# TE-005: Benefit Model Support

## Status

todo

## Priority

P1

## Depends On

- TE-001
- TE-003

## Summary

Add benefit model support for species-level qualitative benefits and tree-level calculated estimates.

This work should make room for ecological, environmental, and economic benefit information without presenting uncertain estimates as precise facts.

## Product Goal

TreeSeek should eventually help users understand the environmental and urban value of trees, including shade, cooling, stormwater, carbon, air quality, habitat, and possible economic impact.

## Design Principle

Separate:

1. general species-level benefit notes, and
2. tree-instance calculated estimates.

A species-level note might say that large-canopied trees can provide shade and wildlife habitat.

A tree-instance estimate might say that a particular 45 cm DBH tree is estimated to provide a modeled amount of stormwater interception or carbon storage.

These are different claim types and should be modeled separately or clearly distinguished with a `scope` field.

## Proposed Scope Values

```text
species
species_region
city
location
tree_instance
```

At minimum, support:

```text
species
tree_instance
```

## Proposed Metric Types

Potential future metric types:

```text
carbon_storage
carbon_sequestration_annual
stormwater_interception_annual
air_pollution_removal_annual
shade_cooling
canopy_contribution
economic_value_annual
ecological_value_note
wildlife_value_note
maintenance_note
```

Do not implement all metrics in the first version unless a source/methodology has been selected.

## Data Requirements

Benefit records should include:

```text
species_id
tree_id, if the estimate is tree-specific
metric_type
scope
value
unit
min_value
max_value
currency, if applicable
region
method_version
assumptions
confidence
source_system
source_url
retrieved_at or calculated_at
license
attribution
```

## User-Facing Requirements

The UI/API must distinguish:

- facts
- estimates
- qualitative notes
- model outputs

The UI should not display dollar values or precise environmental numbers without methodology and caveat text.

## Example API Section

```json
{
  "benefits": {
    "available": true,
    "items": [
      {
        "metric_type": "stormwater_interception_annual",
        "scope": "tree_instance",
        "value": 1200,
        "unit": "litres_per_year",
        "confidence": "low",
        "method_version": "example-model-v1",
        "label": "Estimated annual stormwater interception",
        "caveat": "Estimate based on DBH and model assumptions; not a field measurement."
      }
    ]
  }
}
```

## Non-Goals

- Do not choose a benefits methodology without documenting the decision.
- Do not display precise dollar estimates in the UI as if they are measured facts.
- Do not conflate species-level general benefits with individual-tree modeled estimates.
- Do not block the species profile panel on this work.

## Acceptance Criteria

- Benefit model stores metric type, scope, estimate fields, units, assumptions, method version, confidence, and provenance.
- Model can represent qualitative species-level notes.
- Model can represent calculated tree-instance estimates.
- Null/missing data is handled safely.
- Tests cover fact vs estimate semantics.
- Documentation explains how estimates should be displayed and caveated.
