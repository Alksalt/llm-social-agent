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
            "openai:gpt-4.1-mini",
            "anthropic:claude-3-5-haiku-latest",
            "gemini:gemini-1.5-flash",
        ],
        "draft_x": [
            "openai:gpt-4.1",
            "anthropic:claude-3-7-sonnet-latest",
            "gemini:gemini-1.5-pro",
        ],
        "draft_threads": [
            "openai:gpt-4.1",
            "anthropic:claude-3-7-sonnet-latest",
            "gemini:gemini-1.5-pro",
        ],
        "draft_linkedin": [
            "openai:gpt-4.1",
            "anthropic:claude-3-7-sonnet-latest",
            "gemini:gemini-1.5-pro",
        ],
        "check": [
            "openai:gpt-4.1-nano",
            "anthropic:claude-3-5-haiku-latest",
            "gemini:gemini-1.5-flash-8b",
        ],
    },
    "llm": {
        "temperature": 0.4,
        "max_tokens": 700,
        "timeout_seconds": 30,
    },
    "pricing": {
        "openai:gpt-4.1-mini": {"input_per_1k": 0.0004, "output_per_1k": 0.0016},
        "openai:gpt-4.1": {"input_per_1k": 0.002, "output_per_1k": 0.008},
        "openai:gpt-4.1-nano": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
        "anthropic:claude-3-5-haiku-latest": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
        "anthropic:claude-3-7-sonnet-latest": {"input_per_1k": 0.003, "output_per_1k": 0.015},
        "gemini:gemini-1.5-flash": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
        "gemini:gemini-1.5-flash-8b": {"input_per_1k": 0.00008, "output_per_1k": 0.0003},
        "gemini:gemini-1.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.005},
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
