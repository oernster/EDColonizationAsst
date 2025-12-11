"""Tests for journal and settings API routes (no mocking frameworks, real FS with backup)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException

from src.api import journal as journal_api
from src.api import settings as settings_api
from src.models.api_models import AppSettings


# -----------------------
# /api/journal/status
# -----------------------


@pytest.mark.asyncio
async def test_get_journal_status_with_latest_file(tmp_path: Path):
    """Journal status should return the system from the latest relevant event."""
    journal_dir = tmp_path / "journals"
    journal_dir.mkdir()

    latest_file = journal_dir / "Journal.2025-01-01T000000.01.log"

    # Single Location event is enough to determine current system
    events = [
        json.dumps(
            {
                "timestamp": "2025-01-01T00:00:00Z",
                "event": "Location",
                "StarSystem": "Test System",
                "SystemAddress": 123456,
                "StarPos": [0.0, 0.0, 0.0],
                "Docked": True,
                "StationName": "Test Station",
                "StationType": "Coriolis",
                "MarketID": 42,
            }
        )
    ]
    latest_file.write_text("\n".join(events), encoding="utf-8")

    # Patch get_journal_directory to point at our temp dir
    orig_get_dir = journal_api.get_journal_directory
    try:
        journal_api.get_journal_directory = lambda: journal_dir  # type: ignore[assignment]

        result = await journal_api.get_journal_status()
    finally:
        journal_api.get_journal_directory = orig_get_dir  # type: ignore[assignment]

    assert result["current_system"] == "Test System"


@pytest.mark.asyncio
async def test_get_journal_status_no_files(tmp_path: Path):
    """When no journal files exist, status should report that fact."""
    journal_dir = tmp_path / "journals"
    journal_dir.mkdir()

    orig_get_dir = journal_api.get_journal_directory
    try:
        journal_api.get_journal_directory = lambda: journal_dir  # type: ignore[assignment]
        result = await journal_api.get_journal_status()
    finally:
        journal_api.get_journal_directory = orig_get_dir  # type: ignore[assignment]

    assert result["current_system"] is None
    assert "No journal files found" in result["message"]


@pytest.mark.asyncio
async def test_get_journal_status_handles_errors():
    """Errors from underlying utilities should surface as HTTP 500."""
    def _boom():
        raise FileNotFoundError("no saved games")

    orig_get_dir = journal_api.get_journal_directory
    try:
        journal_api.get_journal_directory = _boom  # type: ignore[assignment]
        with pytest.raises(HTTPException) as exc:
            await journal_api.get_journal_status()
    finally:
        journal_api.get_journal_directory = orig_get_dir  # type: ignore[assignment]

    assert exc.value.status_code == 500


# -----------------------
# /api/settings
# -----------------------


@pytest.mark.asyncio
async def test_get_app_settings_round_trip():
    """get_app_settings should return an AppSettings model with expected fields."""
    settings = await settings_api.get_app_settings()
    assert isinstance(settings, AppSettings)
    # Basic shape assertions
    assert hasattr(settings, "journal_directory")
    assert hasattr(settings, "inara_api_key")
    assert hasattr(settings, "inara_commander_name")


@pytest.mark.asyncio
async def test_update_app_settings_writes_files_and_updates_config(tmp_path: Path):
    """update_app_settings should write config/commander YAML and return updated settings.

    To avoid polluting the real config, this test backs up config.yaml and commander.yaml
    before running and restores them afterwards. It also exercises both the
    'file does not exist' and 'missing section' branches in the implementation.
    """
    # Determine actual paths used by the settings module
    settings_root = Path(settings_api.__file__).resolve().parent.parent.parent
    config_path = settings_root / "config.yaml"
    commander_path = settings_root / "commander.yaml"

    # Backup existing files (if any)
    orig_config = config_path.read_text(encoding="utf-8") if config_path.exists() else None
    orig_commander = commander_path.read_text(encoding="utf-8") if commander_path.exists() else None

    try:
        new_journal_dir = str(tmp_path / "journals")
        app_settings = AppSettings(
            journal_directory=new_journal_dir,
            inara_api_key="TESTKEY",
            inara_commander_name="CMDR Test",
        )

        # ----------------------
        # 1) No existing files: exercise creation branches (lines 34-35, 53-54).
        # ----------------------
        if config_path.exists():
            config_path.unlink()
        if commander_path.exists():
            commander_path.unlink()

        result = await settings_api.update_app_settings(app_settings)

        # Response should echo back the updated settings
        assert isinstance(result, AppSettings)
        assert result.journal_directory == new_journal_dir
        assert result.inara_api_key == "TESTKEY"
        assert result.inara_commander_name == "CMDR Test"

        # Verify config.yaml contents
        assert config_path.exists()
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        assert cfg.get("journal", {}).get("directory") == new_journal_dir

        # Verify commander.yaml contents
        assert commander_path.exists()
        commander = yaml.safe_load(commander_path.read_text(encoding="utf-8")) or {}
        inara_cfg = commander.get("inara", {})
        assert inara_cfg.get("api_key") == "TESTKEY"
        assert inara_cfg.get("commander_name") == "CMDR Test"

        # ----------------------
        # 2) Files exist but missing sections: exercise "journal"/"inara" insertion
        #    branches (lines 41 and 60).
        # ----------------------
        config_path.write_text("{}", encoding="utf-8")
        commander_path.write_text("{}", encoding="utf-8")

        await settings_api.update_app_settings(app_settings)

        cfg2 = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        commander2 = yaml.safe_load(commander_path.read_text(encoding="utf-8")) or {}
        assert "journal" in cfg2
        assert "inara" in commander2
    finally:
        # Restore original config.yaml
        if orig_config is None:
            if config_path.exists():
                config_path.unlink()
        else:
            config_path.write_text(orig_config, encoding="utf-8")

        # Restore original commander.yaml
        if orig_commander is None:
            if commander_path.exists():
                commander_path.unlink()
        else:
            commander_path.write_text(orig_commander, encoding="utf-8")