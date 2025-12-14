"""Configuration management for the application"""

import os
import sys
from pathlib import Path
from typing import List
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file at the top level of the module
load_dotenv()


class JournalConfig(BaseSettings):
    """Journal file configuration"""

    directory: str = Field(
        default=r"C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous",
        description="Path to Elite: Dangerous journal directory",
    )
    watch_interval: float = Field(
        default=1.0, description="File watch interval in seconds"
    )


class ServerConfig(BaseSettings):
    """Server configuration"""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    cors_origins: List[str] = Field(
        default=["http://localhost:5173"], description="Allowed CORS origins"
    )


class WebSocketConfig(BaseSettings):
    """WebSocket configuration"""

    ping_interval: int = Field(
        default=30, description="WebSocket ping interval in seconds"
    )
    reconnect_attempts: int = Field(
        default=5, description="Number of reconnection attempts"
    )


class LoggingConfig(BaseSettings):
    """Logging configuration"""

    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string",
    )


class InaraConfig(BaseSettings):
    """Inara API configuration"""

    api_key: str = os.getenv("INARA_API_KEY", "")
    commander_name: str | None = os.getenv("INARA_COMMANDER_NAME")
    app_name: str = os.getenv("INARA_APP_NAME", "")
    prefer_local_for_commander_systems: bool = Field(
        default=True,
        description=(
            "When true (default), systems where this commander's journals contain "
            "colonization sites are served purely from local journal data. Inara is "
            "only consulted for systems with no local colonization data. When false, "
            "Inara data is preferred wherever it is available."
        ),
    )


class AppConfig(BaseSettings):
    """Main application configuration"""

    journal: JournalConfig = Field(default_factory=JournalConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    inara: InaraConfig = Field(default_factory=InaraConfig)


def _is_frozen() -> bool:
    """
    Return True if the current process is a frozen executable.

    This mirrors the logic in utils.runtime.is_frozen() but is kept local to
    avoid import-time dependencies from this low-level config module.
    """
    # Primary detection: explicit flag set by freezer.
    if bool(getattr(sys, "frozen", False)):
        return True

    # Fallback: argv[0] points at a non-Python .exe
    try:
        exe_path = Path(sys.argv[0])
        if exe_path.suffix.lower() == ".exe" and not exe_path.stem.lower().startswith(
            "python"
        ):
            return True
    except Exception:
        return False

    return False


def _get_user_config_dir() -> Path:
    """
    Return the per-user configuration directory for the packaged runtime.

    On Windows this resolves to %APPDATA%\\EDColonizationAsst.
    On other platforms it follows the XDG base directory spec or falls back
    to ~/.config/EDColonizationAsst.
    """
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            # Pragmatic fallback if APPDATA is missing for some reason.
            base = Path.home() / "AppData" / "Roaming"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            base = Path(xdg)
        else:
            base = Path.home() / ".config"

    return base / "EDColonizationAsst"


def get_config_paths() -> tuple[Path, Path]:
    """
    Compute the locations of config.yaml and commander.yaml.

    - In development (non-frozen) mode we keep using the source layout:
        backend/config.yaml
        backend/commander.yaml

    - In the packaged (frozen) runtime we store configuration alongside
      the installed executable so that the DB, logs and config all live
      under the single install directory (e.g. AppData\Local\EDColonizationAssistant).
    """
    if _is_frozen():
        # Directory containing the running EXE (install root when packaged).
        try:
            base_dir = Path(sys.argv[0]).resolve().parent
        except Exception:
            # Fallback to the original source-layout behaviour if anything goes wrong.
            base_dir = Path(__file__).resolve().parents[2]
    else:
        # backend/src/config.py -> src -> backend
        base_dir = Path(__file__).parent.parent

    config_path = base_dir / "config.yaml"
    commander_path = base_dir / "commander.yaml"
    return config_path, commander_path


# Global config instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        # Resolve configuration file locations in a runtime-aware way.
        # In the packaged EXE we read from a per-user writable directory
        # instead of the (potentially read-only) install location.
        config_path, commander_path = get_config_paths()

        config_dict: dict = {}
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config_dict = yaml.safe_load(f) or {}

        commander_dict: dict = {}
        if commander_path.exists():
            with open(commander_path, "r", encoding="utf-8") as f:
                commander_dict = yaml.safe_load(f) or {}

        inara_cfg = InaraConfig(**commander_dict.get("inara", {}))

        _config = AppConfig(
            journal=JournalConfig(**config_dict.get("journal", {})),
            server=ServerConfig(**config_dict.get("server", {})),
            websocket=WebSocketConfig(**config_dict.get("websocket", {})),
            logging=LoggingConfig(**config_dict.get("logging", {})),
            inara=inara_cfg,
        )

        # Expand user path in journal directory
        _config.journal.directory = os.path.expandvars(_config.journal.directory)

    return _config


def set_config(config: AppConfig) -> None:
    """Set the global configuration instance (mainly for testing)"""
    global _config
    _config = config
