"""API routes for application settings"""

import yaml
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..config import get_config, AppConfig, get_config_paths
from ..models.api_models import AppSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=AppSettings)
async def get_app_settings():
    """Get application settings"""
    config = get_config()
    return AppSettings(
        journal_directory=config.journal.directory,
        inara_api_key=config.inara.api_key,
        inara_commander_name=config.inara.commander_name,
        prefer_local_for_commander_systems=(
            config.inara.prefer_local_for_commander_systems
        ),
    )


@router.post("", response_model=AppSettings)
async def update_app_settings(settings: AppSettings):
    """Update application settings.

    - Non-sensitive config (e.g. journal path) is stored in backend/config.yaml
    - Sensitive commander/Inara config is stored in backend/commander.yaml
    """
    # Resolve config paths in a runtime-aware way so that in the packaged
    # executable we always read/write from a per-user writable directory
    # instead of the (potentially read-only) install location.
    config_path, commander_path = get_config_paths()

    # Update non-sensitive config
    if not config_path.exists():
        # Create a default config if it doesn't exist
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump({"journal": {}}, f)

    with open(config_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    if "journal" not in config_data:
        config_data["journal"] = {}

    config_data["journal"]["directory"] = settings.journal_directory

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, default_flow_style=False)

    # Update sensitive commander/Inara config
    if not commander_path.exists():
        # Create a default commander config if it doesn't exist
        with open(commander_path, "w", encoding="utf-8") as f:
            yaml.dump({"inara": {}}, f)

    with open(commander_path, "r", encoding="utf-8") as f:
        commander_data = yaml.safe_load(f) or {}

    if "inara" not in commander_data:
        commander_data["inara"] = {}

    commander_data["inara"]["api_key"] = settings.inara_api_key or ""
    commander_data["inara"]["commander_name"] = settings.inara_commander_name or ""
    commander_data["inara"][
        "prefer_local_for_commander_systems"
    ] = settings.prefer_local_for_commander_systems

    with open(commander_path, "w", encoding="utf-8") as f:
        yaml.dump(commander_data, f, default_flow_style=False)

    # Update in-memory config so the running app sees the changes
    from ..config import _config

    if _config is not None:
        _config.journal.directory = settings.journal_directory
        _config.inara.api_key = settings.inara_api_key or ""
        _config.inara.commander_name = settings.inara_commander_name
        _config.inara.prefer_local_for_commander_systems = (
            settings.prefer_local_for_commander_systems
        )

    return settings
