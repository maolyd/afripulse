"""AfriPulse command-line interface.

Examples:
    python -m afripulse.orchestration.cli ingest                 # every available source
    python -m afripulse.orchestration.cli ingest worldbank_wdi   # one source

Exit code 0 means every requested source succeeded; 1 means at least one failed.
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
    return parser


def run_ingest(source_ids: Sequence[str]) -> int:
    settings = get_settings()
    log_file = configure_logging(settings.log_level)
    logger.info("Ingesting %s (log file: %s)", list(source_ids), log_file)

    engine = get_engine(settings)
    client = HttpClient(RetryPolicy.from_config(load_sources_config()["defaults"]["http"]))
    failed = []
    try:
        for source_id in source_ids:
            try:
                JOBS[source_id](engine, client)
            except Exception:  # already logged and audited by track_ingestion_run
                failed.append(source_id)
    finally:
        engine.dispose()

    if failed:
        logger.error("Finished with failures: %s", failed)
        return 1
    logger.info("Finished: all %d source(s) succeeded", len(source_ids))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "ingest":
        unknown = sorted(set(args.sources) - JOBS.keys())
        if unknown:
            parser.error(f"unknown source(s) {unknown}; available: {sorted(JOBS)}")
        return run_ingest(args.sources or list(JOBS))
    return 2


if __name__ == "__main__":
    sys.exit(main())
