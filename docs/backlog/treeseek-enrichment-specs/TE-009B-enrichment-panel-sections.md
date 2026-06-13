# TE-009B: Enrichment Sections in Species Panel

## Status

todo

## Priority

P1

## Depends On

- TE-008B
- TE-009A

## Summary

Expand the species profile panel to render the remaining optional enrichment sections such as benefits, risk badges, and media.

This builds on the initial species profile panel rather than replacing it.

Local TreeSeek stats plus summary/source provenance are already part of the current panel and are not the focus of this follow-on task.

## Product Goal

TreeSeek should make species profiles feel locally useful and ecologically informative, not just like embedded Wikipedia summaries.

## Proposed Sections

Potential sections include:

- Summary
- Native or introduced status
- Risk / invasive / pest / pathogen signals
- Ecological value
- Environmental benefits
- Economic or urban benefits
- Species media
- Sources and attribution

## Rendering Principle

Render sections only when data exists.

Missing data should not produce empty headings or broken UI.

Each new third-party section should carry its own source/provenance where applicable.

## Example Layout

```text
Red Oak
Quercus rubra

Summary
[Wikipedia summary]

Status
Native in Ontario

Benefits
Large-canopied trees can provide shade, cooling, and stormwater benefits in urban settings.

Sources
Wikipedia contributors · CC BY-SA 4.0
```

## Non-Goals

- Do not invent benefit or risk values in the frontend.
- Do not show source metadata in a way that overwhelms the main content.
- Do not show precise economic/environmental estimates without caveats.
- Do not require all sections to exist before rendering the panel.

## Acceptance Criteria

- Panel renders optional enrichment sections when present.
- Panel hides missing sections cleanly.
- Risk/native/invasive claims include region context.
- Estimated benefits are labeled as estimates.
- New third-party sections expose source/provenance links when applicable.
- Existing TE-009A profile behavior remains intact.
- UI remains usable on mobile.
