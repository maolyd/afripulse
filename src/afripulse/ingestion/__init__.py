"""Unit tests for the resilient HTTP client.

No internet needed: the network is replaced by a *mock* session that returns
whatever responses each test scripts, and sleeping is replaced by a function
that just records how long the client WOULD have waited.
"""

from unittest.mock import Mock

import pytest
import requests

from afripulse.ingestion.http_client import (
    HttpClient,
    PermanentHTTPError,
    RetryableHTTPError,
    RetryPolicy,
)

URL = "https://api.example.org/data"


def fake_response(status: int, payload=None, text: str = "") -> Mock:
    """A stand-in for requests.Response with only the parts the client uses."""
    response = Mock(status_code=status, text=text)
    response.json.return_value = payload
    return response


def make_client(*responses):
    """Client whose session returns `responses` in order; records sleeps."""
    session = Mock()
    session.get.side_effect = list(responses)
    sleeps: list[float] = []
    client = HttpClient(RetryPolicy(), session=session, sleep=sleeps.append)
    return client, session, sleeps


def test_success_on_first_attempt():
    client, session, sleeps = make_client(fake_response(200, {"ok": True}))

    assert client.get_json(URL) == {"ok": True}
    assert session.get.call_count == 1
    assert sleeps == []


def test_temporary_errors_are_retried_with_exponential_backoff():
    client, session, sleeps = make_client(
        fake_response(503), fake_response(503), fake_response(200, {"ok": True})
    )

    assert client.get_json(URL) == {"ok": True}
    assert session.get.call_count == 3
    assert sleeps == [2, 4]


def test_gives_up_after_max_retries():
    client, session, sleeps = make_client(*[fake_response(503)] * 5)

    with pytest.raises(RetryableHTTPError):
        client.get_json(URL)
    assert session.get.call_count == 5  # 1 attempt + 4 retries
    assert sleeps == [2, 4, 8, 16]


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_errors_are_never_retried(status):
    client, session, sleeps = make_client(fake_response(status, text="Access Denied"))

    with pytest.raises(PermanentHTTPError) as caught:
        client.get_json(URL)
    assert session.get.call_count == 1
    assert sleeps == []
    assert caught.value.status_code == status


def test_permanent_error_keeps_body_excerpt_for_debugging():
    """F-IMF-1: the Akamai reference number must reach the logs."""
    body = "<H1>Access Denied</H1>\n Reference #18.ab37cb17"
    client, _, _ = make_client(fake_response(403, text=body))

    with pytest.raises(PermanentHTTPError, match="Reference #18.ab37cb17"):
        client.get_json(URL)


def test_network_errors_are_retried():
    client, session, sleeps = make_client(
        requests.ConnectionError("connection reset"),
        requests.Timeout("read timed out"),
        fake_response(200, [1, 2, 3]),
    )

    assert client.get_json(URL) == [1, 2, 3]
    assert session.get.call_count == 3
    assert sleeps == [2, 4]


def test_requests_always_use_a_timeout():
    client, session, _ = make_client(fake_response(200, {}))

    client.get_json(URL, {"format": "json"})
    session.get.assert_called_once_with(URL, params={"format": "json"}, timeout=30.0)


def test_policy_is_built_from_sources_config():
    http = {
        "timeout_seconds": 10,
        "max_retries": 2,
        "backoff_base_seconds": 1,
        "retry_on_status": [503],
        "never_retry_status": [403],
    }
    policy = RetryPolicy.from_config(http)

    assert policy == RetryPolicy(
        max_retries=2,
        backoff_base_seconds=1.0,
        timeout_seconds=10.0,
        retry_on_status=frozenset({503}),
    )
