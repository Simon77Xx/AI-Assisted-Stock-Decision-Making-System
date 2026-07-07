"""Helper utilities for resilient akshare data fetching (retry + proxy-bypass)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Callable

logger = logging.getLogger(__name__)


def retry_call(
    fn: Callable[[], Any],
    description: str = "",
    retries: int = 3,
    base_delay: float = 3.0,
) -> Any:
    """Call *fn* with retries and linear backoff.

    Returns the result of *fn* on success.  Re-raises the last exception
    if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                delay = base_delay * attempt
                logger.warning(
                    "%s attempt %d/%d failed: %s — retrying in %.0fs",
                    description or fn.__name__,
                    attempt,
                    retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
    raise last_exc  # type: ignore[misc]


# ── Proxy bypass ─────────────────────────────────────────────────────────

_PROXY_KEYS = ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")


def without_proxy(fn: Callable[[], Any]) -> Any:
    """Temporarily clear all proxy env vars, call *fn*, then restore."""
    saved = {}
    for k in _PROXY_KEYS:
        v = os.environ.pop(k, None)
        saved[k] = v
    try:
        return fn()
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v