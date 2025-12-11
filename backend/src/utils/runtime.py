from __future__ import annotations

"""
Runtime mode detection utilities.

This module centralises the logic for determining whether the application
is running in a regular development environment (Python interpreter +
virtual environment) or as a frozen executable produced by Nuitka.

It is intentionally minimal and side‑effect free so that it can be safely
imported from anywhere in the backend.
"""

import sys
from enum import Enum, auto


class RuntimeMode(Enum):
    """Enumerates the supported runtime modes for the application."""

    DEV = auto()
    FROZEN = auto()


def is_frozen() -> bool:
    """
    Return True if the current process is a frozen executable.

    Nuitka (and other freezer tools) set ``sys.frozen`` on the embedded
    Python interpreter. We use that to distinguish between a packaged
    runtime EXE and a regular Python interpreter invocation.
    """
    return bool(getattr(sys, "frozen", False))


def get_runtime_mode() -> RuntimeMode:
    """
    Determine the current runtime mode.

    Returns
    -------
    RuntimeMode
        ``RuntimeMode.FROZEN`` when running inside a frozen executable,
        otherwise ``RuntimeMode.DEV``.
    """
    return RuntimeMode.FROZEN if is_frozen() else RuntimeMode.DEV