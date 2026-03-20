"""Shared Tenacity retry helper for async ANAF API calls."""

from __future__ import annotations

import logging

import httpx
from tenacity import AsyncRetrying, before_sleep_log, retry_if_exception_type, stop_after_attempt, wait_exponential

from libanaf.config import RetrySettings


def anaf_retrying(settings: RetrySettings, logger: logging.Logger) -> AsyncRetrying:
    """Return a configured ``AsyncRetrying`` context manager for ANAF API calls.

    Args:
        settings: Retry policy (count, delay, backoff_factor, max_delay).
        logger: Logger used for ``before_sleep`` warning messages.

    Returns:
        AsyncRetrying: Configured Tenacity retry context manager.
    """
    return AsyncRetrying(
        stop=stop_after_attempt(settings.count),
        wait=wait_exponential(
            multiplier=settings.backoff_factor,
            min=settings.delay,
            max=settings.max_delay,
        ),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
