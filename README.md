# drzewo

When walking around cities, sometimes you see a tree and want to know what it is.
`drzewo` serves nearby public tree inventory data from city open datasets.

## Quick start

1. Create a PostgreSQL database with PostGIS and apply schema:
   `psql -f drzewo.sql`
2. Copy environment settings:
   `cp .env.example .env`
3. Install dependencies:
   `make setup`
4. Run the app:
   `make run`

The app starts on `http://127.0.0.1:5000`.

## Data loading

Use `tree_loader.py` to import city data:

```bash
.venv/bin/python tree_loader.py toronto --file /path/to/toronto.geojson
.venv/bin/python tree_loader.py ottawa --file /path/to/ottawa.geojson
.venv/bin/python tree_loader.py montreal --file /path/to/montreal.csv
.venv/bin/python tree_loader.py calgary --file /path/to/calgary.csv
.venv/bin/python tree_loader.py waterloo --file /path/to/waterloo.geojson
.venv/bin/python tree_loader.py boston --file /path/to/boston.geojson
.venv/bin/python tree_loader.py markham --file /path/to/markham.geojson
.venv/bin/python tree_loader.py oakville --file /path/to/oakville.geojson
.venv/bin/python tree_loader.py peterborough --file /path/to/peterborough.geojson
```

### Load directly to production DB from your laptop

Create `.env.prod` with production DB credentials, then run:

```bash
make load-prod CITY=toronto FILE=data/toronto/Street\ Tree\ Data.geojson
```

`scripts/load_prod.sh` will:
- source `.env.prod`
- open an SSH tunnel via `drzewo-user` when DB host is local (`127.0.0.1`/`localhost`)
- run `tree_loader.py` against prod DB with batched inserts (`DRZEWO_IMPORT_BATCH_SIZE`, default `2000`)
- print a source row-count verification query

## Quality checks

- `make lint`: static analysis with `ruff`
- `make test`: API smoke tests with `pytest`
- `make check`: lint + tests (recommended pre-commit)

## Agent-friendly workflow

For Codex and other coding agents, use the guardrails in `AGENTS.md`.
Capture session summaries in `docs/agent-log.md`.
