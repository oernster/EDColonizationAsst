"""API routes for application settings"""
import yaml
from pathlib import Path
from fastapi import APIRouter, HTTPException
from ..config import get_config, AppConfig
from ..models.api_models import AppSettings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=AppSettings)
async def get_app_settings():
    """Get application settings"""
    config = get_config()
    return AppSettings(
        journal_directory=config.journal.directory,
        inara_api_key=config.inara.api_key,
        inara_commander_name=config.inara.commander_name
    )


@router.post("", response_model=AppSettings)
async def update_app_settings(settings: AppSettings):
    """Update application settings"""
    config_path = Path(__file__).parent.parent.parent / "config.yaml"

    if not config_path.exists():
        # Create a default config if it doesn't exist
        with open(config_path, 'w') as f:
            yaml.dump({'journal': {}, 'inara': {}}, f)

    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f) or {}

    if 'journal' not in config_data:
        config_data['journal'] = {}
    if 'inara' not in config_data:
        config_data['inara'] = {}

    config_data['journal']['directory'] = settings.journal_directory
    config_data['inara']['api_key'] = settings.inara_api_key
    config_data['inara']['commander_name'] = settings.inara_commander_name

    with open(config_path, 'w') as f:
        yaml.dump(config_data, f, default_flow_style=False)

    # This is a critical step. We need to find a way to make the application aware of the new configuration.
    # A simple approach is to have a global config object that can be updated.
    # For now, we'll rely on the app restarting for the config to be reloaded in a real scenario.
    # In the context of this app, we'll update the global config object.
    
    # Reload config - NOTE: this is a simplified approach for this context.
    # In a real-world scenario, you might have a more robust way of managing config updates without a restart.
    from ..config import _config
    if _config is not None:
        _config.journal.directory = settings.journal_directory
        _config.inara.api_key = settings.inara_api_key
        _config.inara.commander_name = settings.inara_commander_name

    return settings