# AGENTS

This repository is set up for deterministic agent workflows (Codex, Claude Code, Cursor agents, etc.).

## Core workflow

1. Run `make setup` once per machine.
2. Before edits, run `make lint` and `make test` to establish baseline behavior.
3. After edits, run `make check`.
4. Keep changes focused and avoid broad refactors unless requested.

## Project map

- `api.py`: Flask app and API routes.
- `tree_loader.py`: Data import CLI for city datasets.
- `drzewo.sql`: Database schema bootstrap.
- `templates/`, `static/`: Front-end assets.
- `tests/`: Automated checks.

## Environment assumptions

- Python 3.11+.
- PostgreSQL with PostGIS extension.
- `.env` file with database credentials (copy from `.env.example`).

## Commands

- `make setup`: create virtualenv and install dependencies.
- `make run`: run the local server.
- `make lint`: run `ruff` checks.
- `make test`: run `pytest`.
- `make check`: run lint + tests.

## Editing guidance for agents

- Keep database queries parameterized.
- Prefer small, reviewable patches.
- Add or update tests when behavior changes.
- Do not commit credentials or dataset blobs.
