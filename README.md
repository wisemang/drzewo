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

To replace all existing rows for one city source before loading, add `--refresh`:

```bash
.venv/bin/python tree_loader.py oakville --file data/Parks_Tree_Forestry.geojson --refresh
```

Successful and failed imports are recorded in the `import_runs` table with source file, refresh mode, timestamps, and final row count.

### Archive local raw datasets

Keep manually downloaded files in a stable layout under `data/raw/<city>/<YYYY-MM-DD>/` using filesystem metadata for the date:

```bash
make archive-data CITY=oakville FILE=data/Parks_Tree_Forestry.geojson
make archive-data CITY=oakville FILE=data/Parks_Tree_Forestry.geojson APPLY=1
```

The first command is a dry run. Use `APPLY=1` to move the file, `COPY=1` to copy instead, or `DATE=2026-02-18` to override the inferred date.

### Load directly to production DB from your laptop

Create `.env.prod` with production DB credentials, then run:

```bash
make load-prod CITY=toronto FILE=data/toronto/Street\ Tree\ Data.geojson
```

`scripts/load_prod.sh` will:
- source `.env.prod`
- open an SSH tunnel via `drzewo-user` when DB host is local (`127.0.0.1`/`localhost`)
- run `tree_loader.py` against prod DB with batched inserts (`DRZEWO_IMPORT_BATCH_SIZE`, default `2000`)
- pass `--refresh` when `DRZEWO_REFRESH=1`
- print a source row-count verification query

## Log analysis

Analyze Nginx access logs to estimate usage, top endpoints, top IPs, bot-like traffic, and `/nearest` activity:

```bash
make analyze-logs PATHS="/var/log/nginx/access.log /var/log/nginx/access.log*.gz" TOP=15
```

The report uses successful browser-like `/nearest` requests with `lat` and `lng` as a rough daily real-user proxy.

## Quality checks

- `make lint`: static analysis with `ruff`
- `make test`: API smoke tests with `pytest`
- `make check`: lint + tests (recommended pre-commit)

## Agent-friendly workflow

For Codex and other coding agents, use the guardrails in `AGENTS.md`.
Capture session summaries in `docs/agent-log.md`.
