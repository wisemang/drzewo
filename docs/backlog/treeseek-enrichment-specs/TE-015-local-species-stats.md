# TE-015: Local TreeSeek Species Stats

## Status

todo

## Priority

P1

## Depends On

- TE-001
- TE-008A

## Summary

Add local TreeSeek-derived species stats to the species profile API and panel.

This feature uses TreeSeek's own mapped tree database to make species profiles feel local and specific.

## Product Goal

When users open a species profile, they should see how that species appears in the local mapped urban forest, not just a generic species description.

## Example User-Facing Content

```text
In TreeSeek
42 red oaks mapped within 1 km
Largest nearby red oak: 78 cm DBH
Seen in: Toronto, Ottawa
```

## Possible Stats

- Count of same-species trees within selected radius.
- Radius used for nearby count.
- Largest nearby DBH.
- Average or median nearby DBH.
- Cities or datasets where the species appears.
- Count of same-species records in the current city.
- Count of same-species records across all TreeSeek data.

## API Shape

Nearby stats require request context because `/species/<species_id>/profile` alone does not imply a
location. Proposed query parameters:

```http
GET /species/<species_id>/profile?lat=43.65&lng=-79.38&radius_m=1000
```

`radius_m` should be clamped to a documented maximum, following the same cost-control principle as
`/nearest`.

```json
{
  "local_stats": {
    "available": true,
    "context": {
      "scope": "nearby",
      "latitude": 43.65,
      "longitude": -79.38
    },
    "nearby_radius_m": 1000,
    "nearby_count": 42,
    "largest_nearby_dbh_cm": 78,
    "median_nearby_dbh_cm": 34,
    "cities_seen": ["Toronto", "Ottawa"]
  }
}
```

When no `lat`/`lng` is supplied, the API may still return aggregate mapped-record stats such as
`cities_seen` or total records, but should omit or null out nearby-only fields.

## Design Notes

These stats should be clearly presented as TreeSeek database stats, not ecological truths.

For example, "42 red oaks mapped within 1 km" means TreeSeek has 42 mapped records nearby. It does not necessarily mean only 42 red oaks exist nearby.

## Non-Goals

- Do not infer real-world abundance beyond available mapped data.
- Do not make ecological or environmental claims in this task.
- Do not require external data sources.
- Do not block the initial species profile panel on this work.

## Acceptance Criteria

- Species profile API can return same-species counts nearby.
- Nearby calculations require explicit location context such as `lat`, `lng`, and `radius_m`.
- API includes the radius used for nearby calculations.
- API can return largest nearby DBH when available.
- API can return cities/datasets where the species appears.
- Missing DBH values do not break stats calculations.
- Frontend can render local stats when available.
- UI copy makes it clear these are TreeSeek mapped-record stats.
