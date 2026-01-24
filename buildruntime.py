#!/usr/bin/env python3
"""
Build script for packaging the ED Colonisation Assistant runtime into a
self-contained Windows .exe using Nuitka.

This EXE is intended to be the primary entrypoint for end users after
installation, so that they do NOT need a system-wide Python installation.

Key properties:

- Target script:
    backend/src/runtime_entry.py

- Output:
    EDColonisationAsst.exe in the project root.

- Behaviour:
    - In DEV mode (when run via python):
        Delegates to the existing launcher window and virtual environment
        logic so that developers can keep using the current workflow.
    - In FROZEN mode (when running as the EXE built by this script):
        Starts the backend in-process and provides a Qt tray with "Open Web
        UI" and "Exit" actions.

Usage (from project root):

    uv run python buildruntime.py

Nuitka notes:

- We use --onefile for a single exe.
- We enable the pyside6 plugin.
- We use --jobs=N where N is the number of logical cores.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List


APP_NAME = "Elite: Dangerous Colonisation Assistant"
RUNTIME_EXE_NAME = "EDColonisationAsst"


def build_runtime() -> None:
    """Build the runtime executable using Nuitka."""
    project_root = Path(__file__).resolve().parent

    runtime_entry = project_root / "backend" / "src" / "runtime_entry.py"
    if not runtime_entry.exists():
        raise FileNotFoundError(
            f"Could not find runtime_entry.py at: {runtime_entry}\n"
            "Ensure backend/src/runtime_entry.py exists before building the runtime."
        )

    icon_path = project_root / "EDColonisationAsst.ico"
    if not icon_path.exists():
        raise FileNotFoundError(
            f"Could not find EDColonisationAsst.ico at: {icon_path}\n"
            "Place the .ico file in the project root or update buildruntime.py."
        )

    print(f"[buildruntime] Building runtime for {APP_NAME}")
    print(f"[buildruntime] Runtime entry script: {runtime_entry}")
    print(f"[buildruntime] Icon: {icon_path}")

    # Determine jobs for Nuitka parallel compilation.
    cpu_count = os.cpu_count() or 1
    jobs = str(cpu_count)
    print(f"[buildruntime] Using {jobs} parallel jobs for Nuitka compilation")

    # Allow temporarily enabling a visible console for debugging the packaged
    # runtime. When EDCA_DEBUG_CONSOLE=1 (or true/yes/on) is present in the
    # environment at build time, we use "--windows-console-mode=attach" so
    # launching EDColonisationAsst.exe from PowerShell/CMD will show console
    # output. For normal release builds we keep the console disabled.
    debug_console = os.environ.get("EDCA_DEBUG_CONSOLE", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    console_mode = "attach" if debug_console else "disable"
    print(f"[buildruntime] Windows console mode: {console_mode}")

    # Base Nuitka arguments.
    # Notes:
    # - --onefile: single exe.
    # - --standalone is implied by --onefile.
    # - --enable-plugin=pyside6: ensures Qt/PySide6 integration.
    # - --jobs: parallel compilation.
    nuitka_args: List[str] = [
        sys.executable,
        "-m",
        "nuitka",
        "--onefile",
        "--enable-plugin=pyside6",
        f"--jobs={jobs}",
        f"--windows-console-mode={console_mode}",
        f"--output-filename={RUNTIME_EXE_NAME}.exe",
        f"--windows-icon-from-ico={icon_path}",
    ]

    # Finally, the script to compile.
    nuitka_args.append(str(runtime_entry))

    print(f"[buildruntime] Running Nuitka with args:")
    for part in nuitka_args:
        print("  ", part)

    result = subprocess.run(nuitka_args)
    if result.returncode != 0:
        raise RuntimeError(f"Nuitka build failed with exit code {result.returncode}")

    dist_path = project_root / f"{RUNTIME_EXE_NAME}.exe"
    if dist_path.exists():
        print(f"[buildruntime] Runtime build complete: {dist_path}")
    else:
        print(
            "[buildruntime] Build finished, but "
            f"{RUNTIME_EXE_NAME}.exe not found in project root. "
            "Check Nuitka output for details."
        )


def main() -> int:
    try:
        build_runtime()
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[buildruntime] ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
