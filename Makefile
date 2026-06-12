PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PY := $(BIN)/python
RUFF := $(BIN)/ruff
PYTEST := $(BIN)/pytest

.PHONY: help setup install-dev run test lint format check load-prod archive-data download-geneva-data enrich-species-profiles analyze-logs

help:
	@echo "Targets:"
	@echo "  setup       Create venv and install runtime + dev dependencies"
	@echo "  run         Run the Flask app"
	@echo "  test        Run test suite"
	@echo "  lint        Run static checks"
	@echo "  format      Auto-fix style/import issues with ruff"
	@echo "  check       Run lint + tests"
	@echo "  load-prod   Load city data into prod DB from local machine (CITY=... [FILE=...])"
	@echo "  archive-data Archive a local dataset into data/raw/<city>/<date>/ (CITY=... FILE=... APPLY=1)"
	@echo "  download-geneva-data Download Geneva SITG trees into data/raw/geneva/<date>/"
	@echo "  enrich-species-profiles Populate species_profile from Wikipedia (optional SPECIES_KEY=... LIMIT=... REFRESH=1 DRY_RUN=1)"
	@echo "  analyze-logs Analyze Nginx access logs (PATHS=... TOP=...)"

setup:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt

run:
	$(PY) api.py

test:
	$(PYTEST)

lint:
	$(RUFF) check .

format:
	$(RUFF) check . --fix

check: lint test

load-prod:
	@test -n "$(CITY)" || (echo "CITY is required (e.g. CITY=boston)" && exit 1)
	./scripts/load_prod.sh "$(CITY)" "$(FILE)"

archive-data:
	@test -n "$(CITY)" || (echo "CITY is required (e.g. CITY=oakville)" && exit 1)
	@test -n "$(FILE)" || (echo "FILE is required (e.g. FILE=data/Parks_Tree_Forestry.geojson)" && exit 1)
	./scripts/archive_dataset.py "$(CITY)" "$(FILE)" $(if $(DATE),--date "$(DATE)") $(if $(COPY),--copy) $(if $(APPLY),--apply)

download-geneva-data:
	$(PY) scripts/download_geneva_trees.py $(if $(OUTPUT),--output "$(OUTPUT)") $(if $(PAGE_SIZE),--page-size "$(PAGE_SIZE)") $(if $(OVERWRITE),--overwrite)

enrich-species-profiles:
	$(PY) scripts/enrich_species_profiles.py $(if $(SPECIES_KEY),--species-key "$(SPECIES_KEY)") $(if $(LIMIT),--limit "$(LIMIT)") $(if $(REFRESH),--refresh) $(if $(DRY_RUN),--dry-run)

analyze-logs:
	$(PY) -m nginx_log_analysis $(if $(PATHS),$(PATHS)) $(if $(TOP),--top $(TOP))
