"""Elite: Dangerous Colonisation Assistant Backend"""

from __future__ import annotations

from pathlib import Path


def _load_version() -> str:
    """
    Load the application version from the VERSION file.

    Resolution order:
    1. Development / source tree:
       - ../../VERSION relative to backend/src/__init__.py
    2. Frozen/installed runtime:
       - VERSION next to the running executable (sys.executable / sys.argv[0])

    If all lookups fail, falls back to "0.0.0".
    """
    # First, try the source layout: backend/src/__init__.py -> backend -> project root
    try:
        project_root = Path(__file__).resolve().parents[2]
        version_file = project_root / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        # Ignore and fall through to frozen/installed lookup.
        pass

    # Second, try to locate VERSION next to the executable in a frozen build.
    try:
        import sys

        exe_path = Path(getattr(sys, "frozen", False) and sys.executable or sys.argv[0])
        exe_root = exe_path.resolve().parent
        version_file = exe_root / "VERSION"
        if version_file.exists():
            return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        # Ignore and fall through to final default.
        pass

    # Final safe default if nothing worked.
    return "0.0.0"


__version__ = _load_version()
