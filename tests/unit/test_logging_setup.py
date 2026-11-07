"""Unit tests for afripulse.logging_setup (no database needed)."""

import logging

from afripulse.logging_setup import configure_logging


def test_messages_are_written_to_the_log_file(tmp_path):
    log_file = configure_logging("INFO", log_dir=tmp_path)
    logging.getLogger("afripulse.test").info("hello from the test")

    for handler in logging.getLogger().handlers:
        handler.flush()
    assert "hello from the test" in log_file.read_text(encoding="utf-8")


def test_repeated_configuration_does_not_duplicate_handlers(tmp_path):
    configure_logging("INFO", log_dir=tmp_path)
    configure_logging("INFO", log_dir=tmp_path)

    ours = [h for h in logging.getLogger().handlers if getattr(h, "afripulse_handler", False)]
    assert len(ours) == 2  # one console + one file, not four
