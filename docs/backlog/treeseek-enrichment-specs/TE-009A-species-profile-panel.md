# TE-009A: Species Profile Panel

## Status

done

## Priority

P1

## Depends On

- TE-008A

## Summary

Add a user-facing species profile panel that opens from the existing tree popup.

The current popup should remain focused on facts about the specific mapped tree. Species-level information should live in a separate profile panel.

## Product Goal

When a user taps a tree marker, they should see the existing compact tree facts and have a clear way to learn more about that species.

## Design Principle

Separate:

1. tree instance facts, and
2. species-level facts.

The popup answers:

> What is this mapped tree?

The species panel answers:

> What kind of tree is this?

## Popup Changes

Add a link/button below the existing tree details when `species_profile_available` is true.

Preferred copy:

```text
About red oaks
```

Fallback copy:

```text
About this species
```

Example popup:

```text
Red Oak
875 DUFFERIN ST

Botanical name    Quercus rubra
Original name     Oak, red
Diameter          45 cm

About red oaks ->
```

## Naming Change

Consider renaming the existing popup label:

```text
Source name
```

to:

```text
Original name
```

Rationale: "Source name" may sound like the dataset/provider name. "Original name" more clearly means the name as provided by the source dataset.

This rename is optional for this task unless easy.

## Panel Behavior

On click/tap:

- Fetch `/species/<species_id>/profile`.
- Open a species profile panel.
- Render available summary data.
- Show loading state while fetch is in progress.
- Show a graceful fallback when no profile is available.
- Do not break the existing map popup/table flow.

## Responsive Layout

Preferred behavior:

- Mobile: bottom sheet.
- Desktop: side panel, expanded card, or modal-style panel.

Use the simplest implementation consistent with the existing frontend structure.

## Initial Panel Content

Render:

```text
Red Oak
Quercus rubra

[Wikipedia summary paragraph]

Read more on Wikipedia

Source: Wikipedia contributors · CC BY-SA 4.0
```

## Attribution

If Wikipedia summary text is shown, attribution must also be shown.

Acceptable attribution copy:

```text
Summary from Wikipedia contributors, licensed CC BY-SA 4.0.
```

or:

```text
Source: Wikipedia contributors · CC BY-SA 4.0
```

The Wikipedia link should point to the canonical `source_url`.

## Missing-Data Behavior

If no profile is available:

```text
No species profile is available yet.
```

Still show common name and botanical name if available.

If there is no Wikipedia URL, do not render the "Read more on Wikipedia" link.

If there is no attribution/license, do not show imported summary text unless this is explicitly handled elsewhere.

## Non-Goals

- Do not render benefits estimates.
- Do not render risk/invasive/native badges.
- Do not render species images.
- Do not show page ID, Wikidata ID, or internal metadata in the default UI.
- Do not redesign the whole popup.
- Do not replace the existing marker interaction model.

## Acceptance Criteria

- Popup includes an "About [species]" or "About this species" action when profile data is available.
- Clicking the action opens a species profile panel.
- Panel fetches profile data lazily from `/species/<species_id>/profile`.
- Panel renders common name, botanical name, summary, Wikipedia link, and attribution.
- Panel handles loading, missing data, and API errors gracefully.
- Existing popup contents continue to work.
- Existing map browsing remains fast.
- Wikipedia summary is never displayed without visible attribution.
- Mobile layout is usable.

## Future Hooks

The panel should be structured so later sections can be added without a full rewrite:

- local TreeSeek stats
- native/introduced/invasive status
- ecological value
- environmental benefits
- economic benefits
- pest/pathogen risk
- species media
- source/provenance details
