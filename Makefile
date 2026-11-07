# AfriPulse developer commands. Run `make help` to list them.
# Recipe lines must be indented with a TAB character, not spaces.

PY := .venv/bin/python
CLI := $(PY) -m afripulse.orchestration.cli

# dbt runs inside its project folder, with the variables from .env loaded
# (dbt does not read .env itself). profiles.yml in that folder is found automatically.
DBT_DIR := dbt/afripulse
DBT := cd $(DBT_DIR) && set -a && . ../../.env && set +a && ../../.venv/bin/dbt

.DEFAULT_GOAL := help
.PHONY: help db-setup format lint test test-unit coverage ingest ingest-force check \
	dbt-debug dbt-build dbt-freshness dbt-docs pipeline

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

dbt-debug: ## Check dbt can connect to the database
	$(DBT) debug

dbt-build: ## Build and test every dbt model (staging -> intermediate -> marts)
	$(DBT) build

dbt-freshness: ## Warn if any raw source has not been ingested recently
	$(DBT) source freshness

dbt-docs: ## Generate the dbt documentation site and open it (Ctrl+C to stop)
	$(DBT) docs generate
	$(DBT) docs serve --port 8080

pipeline: ingest dbt-build ## Full pipeline: ingest every source, then build and test the warehouse
