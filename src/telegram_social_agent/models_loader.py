"""Loads optional MODELS.md routing hints."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import yaml


def load_models_reference(models_path: str) -> Dict[str, Any]:
    path = Path(models_path)
    if not path.exists():
        return {
            "exists": False,
            "text": "",
            "routing": {},
        }

    text = path.read_text(encoding="utf-8")
    routing: Dict[str, Any] = {}

    # Parse fenced YAML blocks if present and merge any `routing` keys.
    fenced = re.findall(r"```(?:yaml|yml)\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    for block in fenced:
        try:
            parsed = yaml.safe_load(block) or {}
        except yaml.YAMLError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("routing"), dict):
            routing.update(parsed["routing"])

    return {
        "exists": True,
        "text": text,
        "routing": routing,
    }
