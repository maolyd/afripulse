"""AfriPulse command-line interface.

Examples:
    python -m afripulse.orchestration.cli ingest                 # every available source
    python -m afripulse.orchestration.cli ingest worldbank_wdi   # one source
    python -m afripulse.orchestration.cli ingest imf_weo --force # reload even if unchanged
    python -m afripulse.orchestration.cli quality-report         # GREEN / AMBER / RED report

Exit code 0 means success; 1 means a source failed (ingest) or the data quality
status is RED (quality-report), so schedulers such as Airflow mark the task failed.
One failing source does not stop the others: each is attempted and audited.
"""

import argparse
import logging
import sys
from collections.abc import Sequence

from afripulse.config import get_settings
from afripulse.db.connection import get_engine
from afripulse.ingestion.http_client import HttpClient, RetryPolicy
from afripulse.ingestion.jobs import JOBS
from afripulse.logging_setup import configure_logging
from afripulse.sources_config import load_sources_config

logger = logging.getLogger("afripulse.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="afripulse", description="AfriPulse data platform")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("ingest", help="extract sources and load them into raw tables")
    ingest.add_argument(
        "sources", nargs="*", metavar="SOURCE", help=f"source ids (default: all): {sorted(JOBS)}"
    )
    ingest.add_argument(
        "--force", action="store_true", help="reload even if the source release is unchanged"
    )
    commands.add_parser("quality-report", help="build the data quality report (exit 1 if RED)")
    return parser


def run_ingest(source_ids: Sequence[str], force: bool = False) -> int:
    settings = get_settings()
    log_file = configure_logging(settings.log_level)
    logger.info("Ingesting %s force=%s (log file: %s)", list(source_ids), force, log_file)

    engine = get_engine(settings)
    client = HttpClient(RetryPolicy.from_config(load_sources_config()["defaults"]["http"]))
    failed = []
    try:
        for source_id in source_ids:
            try:
                JOBS[source_id](engine, client, force=force)
            except Exception:  # already logged and audited by track_ingestion_run
                failed.append(source_id)
    finally:
        engine.dispose()

    if failed:
        logger.error("Finished with failures: %s", failed)
        return 1
    logger.info("Finished: all %d source(s) succeeded", len(source_ids))
    return 0


def run_quality_report() -> int:
    from afripulse.quality.report import build_report, save_report

    settings = get_settings()
    configure_logging(settings.log_level)
    engine = get_engine(settings)
    try:
        report = build_report(engine)
        path = save_report(engine, report)
    finally:
        engine.dispose()
    print(
        f"Data quality status: {report.status} "
        f"({report.count('RED')} red, {report.count('AMBER')} amber). Report: {path}"
    )
    return 1 if report.status == "RED" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ingest":
        unknown = sorted(set(args.sources) - JOBS.keys())
        if unknown:
            parser.error(f"unknown source(s) {unknown}; available: {sorted(JOBS)}")
        return run_ingest(args.sources or list(JOBS), force=args.force)
    if args.command == "quality-report":
        return run_quality_report()
    return 2


if __name__ == "__main__":
    sys.exit(main())
