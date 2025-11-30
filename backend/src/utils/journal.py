"""Utility functions for handling Elite: Dangerous journal files."""
import os
from pathlib import Path
from typing import Optional

from .windows import get_saved_games_path


def get_journal_directory() -> Path:
    """
    Find the Elite: Dangerous journal directory.
    This function will check the default location for Windows.
    """
    saved_games_path = get_saved_games_path()
    if not saved_games_path:
        raise FileNotFoundError("Could not find the Saved Games directory.")

    journal_path = saved_games_path / "Frontier Developments" / "Elite Dangerous"
    if not journal_path.is_dir():
        raise FileNotFoundError(f"Journal directory not found at {journal_path}")
    return journal_path


def get_latest_journal_file(journal_dir: Path) -> Optional[Path]:
    """Get the latest journal file from the given directory."""
    files = list(journal_dir.glob("Journal.*.log"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)