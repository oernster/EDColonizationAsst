from __future__ import annotations

"""Common runtime utilities shared by the packaged EXE and launcher/tray stack.

This module centralises:

- Lightweight debug logging that writes to a plain text log file next to the
  running executable (or current working directory as a fallback).
- Import of the FastAPI application instance used by the in-process uvicorn
  server in frozen mode.
- Import and initialisation of the backend logging configuration.
- Runtime mode detection via [`RuntimeMode`](backend/src/utils/runtime.py:1)
  and [`get_runtime_mode()`](backend/src/utils/runtime.py:1).

It is deliberately free of any Qt or uvicorn dependencies so that it can be
imported early by both [`runtime_entry`](backend/src/runtime_entry.py:1) and
the supporting runtime modules without creating circular imports.
"""

import sys
from pathlib import Path

from fastapi import FastAPI

# Import FastAPI app and runtime utilities. In normal (package) execution the
# relative imports work (backend.src.runtime.common). In the frozen Nuitka
# onefile build the module is executed as a top-level script so relative
# imports can fail with "attempted relative import with no known parent
# package". We attempt both relative and absolute imports and log any fatal
# failure via _debug_log before re-raising.


def _debug_log(message: str) -> None:
    """Lightweight debug logger for the frozen runtime.

    Writes to EDColonisationAsst-runtime.log next to the EXE so that we can
    see how far startup progresses even if the Qt tray/icon never appears.
    This deliberately does not depend on the backend logging config.
    """
    try:
        try:
            exe_dir = Path(sys.argv[0]).resolve().parent
        except Exception:
            exe_dir = Path.cwd()

        log_path = exe_dir / "EDColonisationAsst-runtime.log"
        with log_path.open("a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        # Never let debug logging break the runtime.
        pass


try:
    try:
        from ..main import app as fastapi_app  # type: ignore[import-not-found]
        from ..utils.logger import get_logger, setup_logging
        from ..utils.runtime import RuntimeMode, get_runtime_mode
    except Exception:
        from backend.src.main import app as fastapi_app  # type: ignore[import-error]
        from backend.src.utils.logger import (  # type: ignore[import-error]
            get_logger,
            setup_logging,
        )
        from backend.src.utils.runtime import (  # type: ignore[import-error]
            RuntimeMode,
            get_runtime_mode,
        )
except Exception as exc:  # pragma: no cover - catastrophic import failure
    _debug_log(
        f"[runtime.common] FATAL importing FastAPI app or runtime utilities: {exc!r}"
    )
    # Re-raise so Nuitka/console still see the failure, but we at least have
    # EDColonisationAsst-runtime.log with the cause.
    raise

# Initialise logging once at import time so that all runtime modules share the
# same configuration and logger hierarchy.
setup_logging()
logger = get_logger(__name__)
