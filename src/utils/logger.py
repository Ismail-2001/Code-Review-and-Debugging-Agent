"""Logging setup with secret masking and structured output."""

from __future__ import annotations

import logging
import re

from rich.logging import RichHandler


class SecretMasker(logging.Filter):
    """Filter to mask sensitive data in logs to prevent accidental exposure."""

    PATTERNS = [
        (r"(sk-)[a-zA-Z0-9]{32,}", r"\1********"),
        (r"(key=)[a-zA-Z0-9_-]{20,}", r"\1********"),
        (r"(token=)[a-zA-Z0-9_-]{20,}", r"\1********"),
        (r"(secret=)[a-zA-Z0-9_-]{20,}", r"\1********"),
        (r"(password=)[^\s&]+", r"\1********"),
        (r"(api_key=)[^\s&]+", r"\1********"),
        (r'["\']sk-[a-zA-Z0-9]{32,}["\']', '"sk-********"'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg)
        return True


def setup_logger(name: str) -> logging.Logger:
    """Set up a structured logger with secret masking."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_time=True)],
    )
    logger = logging.getLogger(name)
    logger.addFilter(SecretMasker())
    return logger
