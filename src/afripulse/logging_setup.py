"""Logging configuration for AfriPulse.

Sends log records to two places:
  - the console, so you can watch a run live;
  - logs/afripulse.log, rotated at 5 MB (5 old files kept), for later debugging.

Usage (once, at program start):
    from afripulse.logging_setup import configure_logging
    configure_logging("INFO")

Then, in any module:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("Loaded %s rows", count)
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from afripulse.config import PROJECT_ROOT

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_FILE_NAME = "afripulse.log"
MAX_LOG_BYTES = 5_000_000
BACKUP_COUNT = 5

# Third-party libraries that are very chatty at INFO/DEBUG level.
NOISY_LIBRARIES = ("urllib3", "requests", "sqlalchemy.engine")


def configure_logging(level: str = "INFO", log_dir: Path | None = None) -> Path:
    """Configure the root logger. Safe to call more than once.

    Returns:
        The path of the log file.
    """
    log_dir = log_dir or PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Remove handlers added by a previous call, so messages are not duplicated.
    for handler in list(root.handlers):
        if getattr(handler, "afripulse_handler", False):
            root.removeHandler(handler)
            handler.close()

    formatter = logging.Formatter(LOG_FORMAT)
    console_handler = logging.StreamHandler()
    file_handler = RotatingFileHandler(
        log_file, maxBytes=MAX_LOG_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    for handler in (console_handler, file_handler):
        handler.setFormatter(formatter)
        handler.afripulse_handler = True
        root.addHandler(handler)

    for name in NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)

    return log_file
