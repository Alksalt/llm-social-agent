"""Configuration loading and defaults."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULT_SETTINGS: Dict[str, Any] = {
    "timezone": "Europe/Oslo",
    "modes": {
        "dry_run": True,
        "llm_enabled": True,
        "approval_required": True,
    },
    "database": {
        "path": "data/telegram_social_agent.db",
    },
    "paths": {
        "style_path": "./STYLE.md",
        "models_path": "./MODELS.md",
    },
    "telegram": {
        "poll_interval_seconds": 1,
    },
    "platforms": {
        "x_enabled": True,
        "threads_enabled": True,
        "linkedin_enabled": True,
    },
    "platform_limits": {
        "x_max_chars": 280,
        "threads_max_chars": 500,
        "linkedin_max_chars": 3000,
    },
    "routing": {
        "summarize": [
            "anthropic:claude-haiku-4-5",
            "openai:gpt-5-mini",
            "gemini:gemini-3-flash-preview",
        ],
        "draft_x": [
            "anthropic:claude-sonnet-4-5",
            "openai:gpt-5.2",
            "gemini:gemini-3-pro-preview",
        ],
        "draft_threads": [
            "anthropic:claude-sonnet-4-5",
            "openai:gpt-5.2",
            "gemini:gemini-3-flash-preview",
        ],
        "draft_linkedin": [
            "anthropic:claude-sonnet-4-5",
            "openai:gpt-5.2",
            "gemini:gemini-3-pro-preview",
        ],
        "check": [
            "openai:gpt-5-nano",
            "anthropic:claude-haiku-4-5",
            "gemini:gemini-2.5-flash-lite",
        ],
    },
    "llm": {
        "temperature": 0.4,
        "max_tokens": 700,
        "timeout_seconds": 30,
    },
    "pricing": {
        "openai:gpt-5.2-pro": {"input_per_1k": 0.021, "output_per_1k": 0.168},
        "openai:gpt-5.2": {"input_per_1k": 0.00175, "output_per_1k": 0.014},
        "openai:gpt-5.1": {"input_per_1k": 0.00125, "output_per_1k": 0.01},
        "openai:gpt-5-mini": {"input_per_1k": 0.00025, "output_per_1k": 0.002},
        "openai:gpt-5-nano": {"input_per_1k": 0.00005, "output_per_1k": 0.0004},
        "anthropic:claude-opus-4.6": {"input_per_1k": 0.005, "output_per_1k": 0.025},
        "anthropic:claude-opus-4.5": {"input_per_1k": 0.005, "output_per_1k": 0.025},
        "anthropic:claude-sonnet-4-5": {"input_per_1k": 0.003, "output_per_1k": 0.015},
        "anthropic:claude-haiku-4-5": {"input_per_1k": 0.001, "output_per_1k": 0.005},
        "gemini:gemini-3-pro-preview": {"input_per_1k": 0.002, "output_per_1k": 0.012},
        "gemini:gemini-2.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.01},
        "gemini:gemini-3-flash-preview": {"input_per_1k": 0.0005, "output_per_1k": 0.003},
        "gemini:gemini-2.5-flash-lite": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
    },
}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(settings_path: str = "config/settings.yaml") -> Dict[str, Any]:
    """Loads settings.yaml and merges it onto defaults."""
    merged = deepcopy(DEFAULT_SETTINGS)
    config_path = Path(settings_path)
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
        merged = _deep_merge(merged, user_cfg)
    return merged


def parse_route(route: str) -> tuple[str, str]:
    """Parses 'provider:model' route strings."""
    if ":" not in route:
        raise ValueError(f"Invalid route format: {route}")
    provider, model = route.split(":", 1)
    return provider.strip(), model.strip()
