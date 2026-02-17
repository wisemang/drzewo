# Agent Session Log

Use this file to keep concise, high-signal notes from AI-assisted development sessions.
Do not log secrets, tokens, or private user data.

## Entry Template

```md
## YYYY-MM-DD - <short title>
- Prompt summary: <1-2 lines>
- Scope: <files/areas touched>
- Decisions: <important choices + why>
- Validation: <commands run + results>
- Follow-ups: <open tasks or "none">
```

## Entries

## 2026-02-16 - PWA baseline and home-screen icon iteration
- Prompt summary: Add first-pass PWA support (manifest, service worker, offline shell) and improve mobile home-screen icon behavior.
- Scope: `api.py`, `templates/index.html`, `static/js/script.js`, `static/manifest.webmanifest`, `static/sw.js`, `static/offline.html`, `static/images/`.
- Decisions: Added manifest/service-worker/offline routes and registration, iOS web-app meta tags, generated install icon sizes, and used versioned icon filenames + cache bump (`treeseek-v3`) to reduce stale icon caching.
- Validation: `make lint` passed; `make test` passed (`6 passed`).
- Follow-ups: If icon still appears stale on iOS, rotate icon filenames again and reinstall from Safari.

## 2026-02-16 - Persist map fullscreen preference
- Prompt summary: Remember fullscreen mode across page reloads.
- Scope: `static/js/script.js`.
- Decisions: Added `localStorage` persistence (`treeseek.map.fullscreen`) with safe read/write wrappers and automatic restore after map controls initialize.
- Validation: `make lint` passed; `make test` passed (`6 passed`).
- Follow-ups: none.

## 2026-02-16 - Lint remediation and style normalization
- Prompt summary: Fix failing lint gate and confirm tests remain green.
- Scope: `api.py`, `tree_loader.py`, `tests/conftest.py`.
- Decisions: Applied Ruff auto-fixes for import ordering/unused imports, then manually fixed residual long-line and trailing-whitespace findings with no behavioral changes.
- Validation: `make lint` passed; `make test` passed (`6 passed`).
- Follow-ups: none.

## 2026-02-16 - Safer fullscreen transition polish
- Prompt summary: Improve fullscreen transition feel without reintroducing map interaction glitches.
- Scope: `static/css/styles.css`, `static/js/script.js`.
- Decisions: Animated only non-map UI (`header`, intro/details) with opacity/slide, kept map geometry changes instant, and switched to a single `map.invalidateSize({ pan: false })` on next frame.
- Validation: `make test` passed (`6 passed`).
- Follow-ups: Optionally test on older iOS Safari devices for touch behavior parity.

## 2026-02-16 - API query guardrails for nearest-tree lookup
- Prompt summary: Add API-side input and query guardrails to protect latency and stability.
- Scope: `api.py`, `tests/test_api.py`.
- Decisions: Added coordinate bounds validation, bounded `limit`, optional bounded `max_distance_m` radius filter (`ST_DWithin`), and explicit 400 responses for invalid parameters.
- Validation: `make test` passed (`6 passed`).
- Follow-ups: Optional: add request-level latency logging for `/nearest` in production.

## 2026-02-16 - Additive marker lifecycle with mobile-safe cap
- Prompt summary: Keep marker behavior additive to avoid visual churn, while protecting map performance on older phones.
- Scope: `static/js/script.js`.
- Decisions: Switched to additive marker persistence with dedupe by stable key and FIFO pruning only after a cap (`MAX_PERSISTENT_MARKERS=600`) is exceeded; retained marker sync metrics logging.
- Validation: `make test` passed (`3 passed`).
- Follow-ups: Tune marker cap using real-device profiling if needed.

## 2026-02-16 - Map fullscreen mode and icon polish
- Prompt summary: Add a map-only fullscreen toggle and refine the exit icon to use provided SVG.
- Scope: `templates/index.html`, `static/css/styles.css`, `static/js/script.js`.
- Decisions: Implemented app-level fullscreen mode that hides header/table content, added a dedicated map control toggle, kept `⛶` for enter, and switched exit icon to inline Bootstrap `fullscreen-exit` SVG.
- Validation: `make test` passed (`3 passed`).
- Follow-ups: none.

## 2026-02-16 - Read latency schema improvements
- Prompt summary: Improve read latency without changing geometry type semantics.
- Scope: `drzewo.sql`, `tree_loader.py`.
- Decisions: Added GiST index on `street_trees.geom`, enforced `NOT NULL` on `source/objectid/geom`, and run post-import `ANALYZE` after successful commits.
- Validation: `python3 -m compileall tree_loader.py` passed.
- Follow-ups: Apply equivalent `ALTER TABLE` + `CREATE INDEX CONCURRENTLY` statements on existing databases.

## 2026-02-15 - Agent coding baseline
- Prompt summary: Set up repo optimally for agent-based coding.
- Scope: `Makefile`, `pyproject.toml`, `requirements-dev.txt`, `README.md`, `AGENTS.md`, `tests/`, `.env.example`, `api.py`.
- Decisions: Standardized command surface (`make setup/check/run`), added lint/test defaults, and added smoke tests for API behavior.
- Validation: `python3 -m compileall api.py tree_loader.py tests/test_api.py` passed. Full dependency install/check not run in sandboxed no-network environment.
- Follow-ups: Run `make check` in normal networked dev environment.
