PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
PIP := $(BIN)/pip
PY := $(BIN)/python
RUFF := $(BIN)/ruff
PYTEST := $(BIN)/pytest

.PHONY: help setup install-dev run test lint format check

help:
	@echo "Targets:"
	@echo "  setup       Create venv and install runtime + dev dependencies"
	@echo "  run         Run the Flask app"
	@echo "  test        Run test suite"
	@echo "  lint        Run static checks"
	@echo "  format      Auto-fix style/import issues with ruff"
	@echo "  check       Run lint + tests"

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
