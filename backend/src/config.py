"""Configuration management for the application"""
from pathlib import Path
from typing import List
import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


class JournalConfig(BaseSettings):
    """Journal file configuration"""
    directory: str = Field(
        default=r"C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous",
        description="Path to Elite: Dangerous journal directory"
    )
    watch_interval: float = Field(default=1.0, description="File watch interval in seconds")


class ServerConfig(BaseSettings):
    """Server configuration"""
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    cors_origins: List[str] = Field(
        default=["http://localhost:5173"],
        description="Allowed CORS origins"
    )


class WebSocketConfig(BaseSettings):
    """WebSocket configuration"""
    ping_interval: int = Field(default=30, description="WebSocket ping interval in seconds")
    reconnect_attempts: int = Field(default=5, description="Number of reconnection attempts")


class LoggingConfig(BaseSettings):
    """Logging configuration"""
    level: str = Field(default="INFO", description="Logging level")
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format string"
    )


class InaraConfig(BaseSettings):
    """Inara API configuration"""
    api_key: str = Field(default="", description="Inara.cz API key")
    commander_name: str | None = Field(default=None, description="Commander name")

class AppConfig(BaseSettings):
    """Main application configuration"""
    journal: JournalConfig = Field(default_factory=JournalConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    websocket: WebSocketConfig = Field(default_factory=WebSocketConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    inara: InaraConfig = Field(default_factory=InaraConfig)

    @classmethod
    def load_from_yaml(cls, config_path: Path) -> "AppConfig":
        """Load configuration from YAML file"""
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        
        return cls(
            journal=JournalConfig(**config_dict.get('journal', {})),
            server=ServerConfig(**config_dict.get('server', {})),
            websocket=WebSocketConfig(**config_dict.get('websocket', {})),
            logging=LoggingConfig(**config_dict.get('logging', {})),
            inara=InaraConfig(**config_dict.get('inara', {}))
        )


# Global config instance
_config: AppConfig | None = None


def get_config() -> AppConfig:
    """Get the global configuration instance"""
    global _config
    if _config is None:
        config_path = Path(__file__).parent.parent / "config.yaml"
        if config_path.exists():
            _config = AppConfig.load_from_yaml(config_path)
        else:
            _config = AppConfig()
    return _config


def set_config(config: AppConfig) -> None:
    """Set the global configuration instance (mainly for testing)"""
    global _config
    _config = config