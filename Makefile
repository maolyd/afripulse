# AfriPulse developer commands. Run `make help` to list them.
# Recipe lines must be indented with a TAB character, not spaces.

PY := .venv/bin/python
CLI := $(PY) -m afripulse.orchestration.cli

# dbt runs inside its project folder, with the variables from .env loaded
# (dbt does not read .env itself). profiles.yml in that folder is found automatically.
DBT_DIR := dbt/afripulse
DBT := cd $(DBT_DIR) && set -a && . ../../.env && set +a && ../../.venv/bin/dbt

# Airflow lives in its OWN virtual environment (it pins libraries that conflict
# with dbt). It runs project commands through the main .venv (see the DAG).
AIRFLOW_VERSION := 3.3.2
AIRFLOW_CONSTRAINTS_URL := https://raw.githubusercontent.com/apache/airflow/constraints-$(AIRFLOW_VERSION)/constraints-3.12.txt
# Airflow's official constraints pin 3 packages that publish NO wheel for Intel
# Macs on macOS 12 (pip would have to compile them, which needs Rust). Verified with
#   pip download --platform macosx_12_0_x86_64 --python-version 3.12 --only-binary=:all:
# Override them with the newest versions that do, all within Airflow's requirements
# (libcst>=1.8.2, cryptography>=44.0.3, lazy-object-proxy>=1.2.0).
AIRFLOW_INTEL_MAC_PINS := s/^libcst==.*/libcst==1.8.6/; s/^cryptography==.*/cryptography==48.0.1/; s/^lazy-object-proxy==.*/lazy-object-proxy==1.11.0/
# AIRFLOW_HOME: config, metadata DB and logs stay inside the project (git-ignored).
# OBJC_DISABLE_INITIALIZE_FORK_SAFETY / no_proxy: avoid known macOS crashes when
# Airflow starts task processes. PATH: standalone starts its parts as `airflow ...`.
AIRFLOW := export AIRFLOW_HOME="$(CURDIR)/airflow" AIRFLOW__CORE__LOAD_EXAMPLES=False \
	OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES no_proxy='*' \
	PATH="$(CURDIR)/.venv-airflow/bin:$$PATH" &&

.DEFAULT_GOAL := help
.PHONY: help db-setup format lint test test-unit coverage ingest ingest-force check \
	dbt-debug dbt-build dbt-full-refresh dbt-freshness dbt-docs pipeline \
	airflow-install airflow-init airflow-start airflow-password airflow-test \
	quality-report

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

dbt-full-refresh: ## Rebuild every model from scratch (after changing an incremental model's logic)
	$(DBT) build --full-refresh

dbt-freshness: ## Warn if any raw source has not been ingested recently
	$(DBT) source freshness

dbt-docs: ## Generate the dbt documentation site and open it (Ctrl+C to stop)
	$(DBT) docs generate
	$(DBT) docs serve --port 8081

quality-report: ## Data quality report (GREEN / AMBER / RED) in reports/data_quality/latest.md
	$(CLI) quality-report

pipeline: ingest dbt-freshness dbt-build quality-report ## Full pipeline: ingest, freshness, dbt build, quality report

airflow-install: ## Create .venv-airflow and install Airflow with its tested constraints (once)
	python3.12 -m venv .venv-airflow
	.venv-airflow/bin/python -m pip install --upgrade pip
	mkdir -p airflow
	curl -fsSL "$(AIRFLOW_CONSTRAINTS_URL)" | sed -E '$(AIRFLOW_INTEL_MAC_PINS)' > airflow/constraints.txt
	@grep -E '^(libcst|cryptography|lazy-object-proxy)==' airflow/constraints.txt
	.venv-airflow/bin/python -m pip install --only-binary=:all: \
		"apache-airflow==$(AIRFLOW_VERSION)" pytest --constraint airflow/constraints.txt

airflow-init: ## Create Airflow's metadata database in airflow/ (safe to re-run)
	$(AIRFLOW) airflow db migrate

airflow-start: ## Start Airflow (UI on http://localhost:8080). Ctrl+C to stop
	$(AIRFLOW) airflow standalone

airflow-password: ## Show the Airflow UI login (user: admin)
	@cat airflow/simple_auth_manager_passwords.json.generated; echo

airflow-test: ## Test the DAGs with Airflow's own environment
	$(AIRFLOW) PYTHONPATH=airflow/dags python -m pytest -q -p no:cacheprovider tests/dags
