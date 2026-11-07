# AfriPulse developer commands. Run `make help` to list them.
# Recipe lines must be indented with a TAB character, not spaces.

PY := .venv/bin/python
CLI := $(PY) -m afripulse.orchestration.cli

.DEFAULT_GOAL := help
.PHONY: help db-setup format lint test test-unit coverage ingest ingest-force check

help: ## List available commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  make %-14s %s\n", $$1, $$2}'

db-setup: ## Create or update the database, roles, schemas and tables (idempotent)
	psql -d postgres -v ON_ERROR_STOP=1 -q -f sql/ddl/001_create_database.sql
	psql -d postgres -v ON_ERROR_STOP=1 -q -f sql/ddl/002_create_roles.sql
	for f in $$(ls sql/ddl/*.sql | grep -v -e /001_ -e /002_); do \
		psql -d afripulse -v ON_ERROR_STOP=1 -q -f $$f || exit 1; \
	done

format: ## Auto-format the code
	$(PY) -m ruff format src tests scripts

lint: ## Check code style and common bugs
	$(PY) -m ruff check .

test: ## Run all tests (needs PostgreSQL running)
	$(PY) -m pytest -q

test-unit: ## Run unit tests only (no database needed)
	$(PY) -m pytest -q -m "not integration"

coverage: ## Run all tests with a coverage report (fails under 80%)
	$(PY) -m pytest -q --cov=afripulse --cov-report=term-missing --cov-report=html

ingest: ## Load every source (skips unchanged ones)
	$(CLI) ingest

ingest-force: ## Reload every source even if unchanged
	$(CLI) ingest --force

check: lint test ## Lint + tests: run before every commit
