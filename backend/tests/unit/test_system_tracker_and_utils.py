"""Unit tests for SystemTracker and utility modules (no mocking)."""

from datetime import datetime, UTC
from pathlib import Path
import logging
import os

import pytest

from src.models.journal_events import LocationEvent, FSDJumpEvent, DockedEvent
from src.services.system_tracker import SystemTracker
from src.utils.journal import get_latest_journal_file
from src.utils.logger import setup_logging, get_logger
from src.utils.windows import get_saved_games_path


# -----------------------
# SystemTracker tests
# -----------------------


def _make_location_event(
    star_system: str,
    docked: bool,
    station_name: str | None = None,
    station_type: str | None = None,
) -> LocationEvent:
    return LocationEvent(
        timestamp=datetime.now(UTC),
        event="Location",
        star_system=star_system,
        system_address=123456,
        star_pos=[0.0, 0.0, 0.0],
        station_name=station_name,
        station_type=station_type,
        market_id=42 if docked else None,
        docked=docked,
        raw_data={},
    )


def _make_fsd_jump_event(star_system: str) -> FSDJumpEvent:
    return FSDJumpEvent(
        timestamp=datetime.now(UTC),
        event="FSDJump",
        star_system=star_system,
        system_address=654321,
        star_pos=[1.0, 2.0, 3.0],
        jump_dist=10.5,
        fuel_used=3.0,
        fuel_level=5.0,
        raw_data={},
    )


def _make_docked_event(star_system: str, station_name: str) -> DockedEvent:
    return DockedEvent(
        timestamp=datetime.now(UTC),
        event="Docked",
        station_name=station_name,
        station_type="Outpost",
        star_system=star_system,
        system_address=777,
        market_id=999,
        station_faction={"Name": "Test Faction"},
        station_government="Democracy",
        station_economy="Industrial",
        station_economies=[],
        raw_data={},
    )


def test_system_tracker_initial_state():
    tracker = SystemTracker()
    assert tracker.get_current_system() is None
    assert tracker.get_current_station() is None
    assert tracker.is_docked() is False


def test_system_tracker_update_from_location_docked():
    tracker = SystemTracker()
    event = _make_location_event(
        "Test System", docked=True, station_name="Test Station", station_type="Coriolis"
    )

    tracker.update_from_location(event)

    assert tracker.get_current_system() == "Test System"
    assert tracker.get_current_station() == "Test Station"
    assert tracker.is_docked() is True


def test_system_tracker_update_from_location_undocked():
    tracker = SystemTracker()
    event = _make_location_event("Deep Space", docked=False)

    tracker.update_from_location(event)

    assert tracker.get_current_system() == "Deep Space"
    assert tracker.get_current_station() is None
    assert tracker.is_docked() is False


def test_system_tracker_update_from_jump_clears_dock():
    tracker = SystemTracker()
    # Start docked
    dock_event = _make_docked_event("Origin System", "Origin Station")
    tracker.update_from_docked(dock_event)
    assert tracker.is_docked() is True

    # Jump away
    jump_event = _make_fsd_jump_event("Destination System")
    tracker.update_from_jump(jump_event)

    assert tracker.get_current_system() == "Destination System"
    assert tracker.get_current_station() is None
    assert tracker.is_docked() is False


def test_system_tracker_update_from_docked_sets_state():
    tracker = SystemTracker()
    event = _make_docked_event("Dock System", "Dock Station")

    tracker.update_from_docked(event)

    assert tracker.get_current_system() == "Dock System"
    assert tracker.get_current_station() == "Dock Station"
    assert tracker.is_docked() is True


# -----------------------
# Utils: journal
# -----------------------


def test_get_latest_journal_file_returns_latest(tmp_path: Path):
    """Ensure get_latest_journal_file picks the newest Journal.*.log by mtime."""
    journal_dir = tmp_path
    older = journal_dir / "Journal.2025-01-01T000000.01.log"
    newer = journal_dir / "Journal.2025-01-02T000000.01.log"

    older.write_text("old", encoding="utf-8")
    newer.write_text("new", encoding="utf-8")

    # Explicitly control modification times to avoid filesystem resolution issues
    older_time = 1_700_000_000  # arbitrary but stable epoch times
    newer_time = older_time + 100

    os.utime(older, (older_time, older_time))
    os.utime(newer, (newer_time, newer_time))

    latest = get_latest_journal_file(journal_dir)
    assert latest is not None
    assert latest.name == newer.name


def test_get_latest_journal_file_empty_dir(tmp_path: Path):
    """Empty directory should yield None."""
    latest = get_latest_journal_file(tmp_path)
    assert latest is None


# -----------------------
# Utils: windows + logger
# -----------------------


def test_get_saved_games_path_does_not_crash():
    """get_saved_games_path should never raise; it may legitimately return None."""
    path = get_saved_games_path()
    assert path is None or isinstance(path, Path)


def test_setup_logging_and_get_logger():
    """setup_logging and get_logger should be callable without errors."""
    setup_logging(level="DEBUG", format_str="%(levelname)s:%(name)s:%(message)s")
    logger = get_logger("test_logger_system")
    assert isinstance(logger, logging.Logger)
    logger.debug("This is a debug message from test_setup_logging_and_get_logger")
