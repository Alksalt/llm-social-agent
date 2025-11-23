# src/core/config_loader.py

"""
Configuration loading utilities.

This module is responsible for:
- Loading environment variables from a .env file (for secrets, keys, URLs).
- Loading non-secret configuration from a YAML file (config/settings.yaml).
- Providing a simple function to get a merged configuration dictionary.

Keeping config here avoids hardcoding secrets or settings throughout the code.
"""

from pathlib import Path
from dotenv import load_dotenv
import os
import yaml

BASE_DIR = Path(__file__).resolve().parents[2]
    
def load_environment() -> None:
    """
    Load environment variables from the .env file at project root.

    This should be called once near program startup, before reading any env-based config.
    """
    env_path = BASE_DIR / ".env"
    load_dotenv(env_path)

def load_yaml_config() -> dict: 
    """
    Load configuration from config/settings.yaml.

    Returns:
        A dict representing the YAML configuration.
    """
    config_path = BASE_DIR / "config" / "settings.yaml" 
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config

def get_config() -> dict:
    """
    High-level helper that:
    - Ensures environment variables are loaded from .env,
    - Loads YAML config,
    - Merges in environment-based overrides (if we want any).

    Returns:
        A dict representing the full configuration for the application.
    """
    load_environment()
    yaml_config = load_yaml_config()
    db_url_env = os.getenv("DATABASE_URL")

    if db_url_env:
        yaml_config.setdefault("database", {})
        yaml_config["database"]["url"] = db_url_env
    return yaml_config