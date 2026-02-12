"""Logging utilities for the operator training system."""

from __future__ import annotations

import logging
from typing import Optional

_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(name: str = "operator-training") -> logging.Logger:
    """Return a module-level logger configured for Streamlit usage."""
    if name in _LOGGERS:
        return _LOGGERS[name]

    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    _LOGGERS[name] = logger
    return logger


def reset_logger(name: str) -> None:
    """Remove cached loggers, useful for testing."""
    existing: Optional[logging.Logger] = _LOGGERS.pop(name, None)
    if existing:
        for handler in list(existing.handlers):
            existing.removeHandler(handler)
            handler.close()
