"""Resilient HTTP client shared by every API extractor.

Retries only *temporary* failures, with exponential backoff:
  - network problems (connection errors, timeouts);
  - HTTP statuses that mean "try again later" (429, 500, 502, 503, 504).

Never retries *permanent* failures (400, 401, 403, 404...): the server has
already said no, and asking again only adds load (discovery finding F-IMF-1).

Usage:
    client = HttpClient(RetryPolicy.from_config(config["defaults"]["http"]))
    payload = client.get_json("https://api.worldbank.org/v2/country", {"format": "json"})
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests
from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

MAX_WAIT_SECONDS = 60
BODY_EXCERPT_LENGTH = 300


class RetryableHTTPError(Exception):
    """A temporary HTTP failure that is worth retrying."""

    def __init__(self, status_code: int, url: str) -> None:
        super().__init__(f"HTTP {status_code} (temporary) for {url}")
        self.status_code = status_code
        self.url = url


class PermanentHTTPError(Exception):
    """An HTTP failure that retrying cannot fix."""

    def __init__(self, status_code: int, url: str, body_excerpt: str) -> None:
        super().__init__(f"HTTP {status_code} (permanent) for {url}: {body_excerpt}")
        self.status_code = status_code
        self.url = url
        self.body_excerpt = body_excerpt


# Errors that trigger a retry. Anything else stops immediately.
RETRYABLE_EXCEPTIONS = (RetryableHTTPError, requests.ConnectionError, requests.Timeout)


@dataclass(frozen=True)
class RetryPolicy:
    """How patient the client is. Values come from config/sources.yml."""

    max_retries: int = 4
    backoff_base_seconds: float = 2.0
    timeout_seconds: float = 30.0
    retry_on_status: frozenset[int] = frozenset({429, 500, 502, 503, 504})

    @classmethod
    def from_config(cls, http: dict[str, Any]) -> "RetryPolicy":
        """Build a policy from the `defaults.http` section of sources.yml."""
        return cls(
            max_retries=int(http["max_retries"]),
            backoff_base_seconds=float(http["backoff_base_seconds"]),
            timeout_seconds=float(http["timeout_seconds"]),
            retry_on_status=frozenset(http["retry_on_status"]),
        )


class HttpClient:
    """GET JSON from APIs with timeouts, retries and clear errors."""

    def __init__(
        self,
        policy: RetryPolicy | None = None,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.policy = policy or RetryPolicy()
        self.session = session or requests.Session()
        self._sleep = sleep  # injectable, so tests do not really wait

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET `url` and return the decoded JSON, retrying temporary failures."""
        retryer = Retrying(
            stop=stop_after_attempt(self.policy.max_retries + 1),  # first try + retries
            wait=wait_exponential(
                multiplier=self.policy.backoff_base_seconds, max=MAX_WAIT_SECONDS
            ),
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            before_sleep=self._log_retry,
            sleep=self._sleep,
            reraise=True,  # after the last attempt, raise the real error, not a wrapper
        )
        return retryer(self._get_once, url, params)

    def _get_once(self, url: str, params: dict[str, Any] | None) -> Any:
        response = self.session.get(url, params=params, timeout=self.policy.timeout_seconds)
        status = response.status_code

        if status in self.policy.retry_on_status:
            raise RetryableHTTPError(status, url)
        if status >= 400:
            excerpt = " ".join(response.text[:BODY_EXCERPT_LENGTH].split())
            raise PermanentHTTPError(status, url, excerpt)

        logger.debug("GET %s -> %s", url, status)
        return response.json()

    @staticmethod
    def _log_retry(state: RetryCallState) -> None:
        url = state.args[0] if state.args else "?"
        error = state.outcome.exception() if state.outcome else None
        wait = state.next_action.sleep if state.next_action else 0
        logger.warning(
            "Attempt %d failed for %s (%s). Retrying in %.0fs",
            state.attempt_number,
            url,
            error,
            wait,
        )
