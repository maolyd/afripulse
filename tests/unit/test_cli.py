"""Unit tests for the command-line argument handling (no database needed)."""

import pytest

from afripulse.orchestration.cli import main


def test_unknown_source_is_rejected_with_usage_error(capsys):
    with pytest.raises(SystemExit) as exit_info:
        main(["ingest", "not_a_source"])

    assert exit_info.value.code == 2
    assert "unknown source" in capsys.readouterr().err


def test_a_command_is_required():
    with pytest.raises(SystemExit):
        main([])


def test_force_flag_is_parsed():
    from afripulse.orchestration.cli import build_parser

    args = build_parser().parse_args(["ingest", "imf_weo", "--force"])

    assert args.sources == ["imf_weo"]
    assert args.force is True
