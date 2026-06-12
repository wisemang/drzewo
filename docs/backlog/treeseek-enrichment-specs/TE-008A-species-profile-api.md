# TE-008A: Species Profile API

## Status

todo

## Priority

P1

## Depends On

- TE-004

## Summary

Add and document the species profile API response contract for currently available species profile data.

This work exposes the existing Wikipedia-backed `species_profile` enrichment through `/species/<species_id>/profile` in a way that is stable, null-safe, provenance-aware, and ready for future enrichment sections.

## Product Goal

When a user opens a species profile from a tree popup, the frontend should be able to retrieve a compact, trustworthy profile for that species without requiring `/nearest` to return full enrichment payloads.

## Non-Goals

- Do not add benefits estimates in this task.
- Do not add invasive/native/risk data in this task.
- Do not add species imagery in this task.
- Do not expand `/nearest` with full profile summaries.
- Do not expose internal metadata such as Wikipedia page ID as primary user-facing UI content.

## Endpoint

Preferred endpoint:

```http
GET /species/<species_id>/profile
```

If needed for development/debugging, a query-based endpoint may also exist:

```http
GET /species/profile?botanical_name=Quercus%20rubra
```

But the frontend should prefer the stable `species_id` path.

## `/nearest` Contract

`/nearest` should remain optimized for fast map browsing.

It may include only compact species profile metadata:

```json
{
  "objectid": 123,
  "common_name": "Red Oak",
  "botanical_name": "Quercus rubra",
  "original_common_name": "Oak, red",
  "dbh": 45,
  "address": "875 DUFFERIN ST",
  "species_id": 214,
  "species_key": "quercus_rubra",
  "species_profile_available": true
}
```

Treat this as a proposed compact addition to the current `/nearest` response, not a breaking rename
of existing fields. Do not embed the full Wikipedia summary in `/nearest`.

## Profile Response Shape

Initial response shape:

```json
{
  "species_id": 214,
  "species_key": "quercus_rubra",
  "common_name": "Red Oak",
  "botanical_name": "Quercus rubra",
  "sections": {
    "summary": {
      "available": true,
      "text": "Short species summary text...",
      "source_system": "wikipedia",
      "source_url": "https://en.wikipedia.org/wiki/Quercus_rubra",
      "source_title": "Quercus rubra",
      "license": "Creative Commons Attribution-ShareAlike 4.0 International",
      "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
      "attribution": "Wikipedia contributors",
      "confidence": "source-derived",
      "retrieved_at": "2026-06-12T00:00:00+00:00",
      "method_version": "wikipedia-summary-v1"
    },
    "benefits": null,
    "risk": null,
    "media": null,
    "local_stats": null
  }
}
```

## Error and Missing-Data Behavior

If the species exists but has no profile:

```json
{
  "species_id": 214,
  "species_key": "quercus_rubra",
  "common_name": "Red Oak",
  "botanical_name": "Quercus rubra",
  "sections": {
    "summary": null,
    "benefits": null,
    "risk": null,
    "media": null,
    "local_stats": null
  }
}
```

If the species ID does not exist, return a normal API 404 response.

## Acceptance Criteria

- `/species/<species_id>/profile` returns numeric species id, stable species key, species common name, botanical name, summary section, source URL, license, attribution, confidence, retrieval timestamp, and method version.
- Response is null-safe when profile data is missing.
- `/nearest` does not return full profile summaries.
- API response is documented.
- Tests cover known species with profile data.
- Tests cover known species without profile data.
- Tests cover unknown species ID.
- Tests cover Wikipedia attribution and license fields.
- Future sections such as `benefits`, `risk`, `media`, and `local_stats` can be added without breaking existing clients.

## Implementation Notes

- Treat Wikipedia as one enrichment source, not the entire species model.
- Keep provenance attached to the section it supports.
- The frontend should not need to know internal database table names.
- Prefer section-level provenance because future sections will come from different sources.
