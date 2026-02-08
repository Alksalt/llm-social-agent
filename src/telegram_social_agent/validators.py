"""Platform validation and safe truncation."""

from __future__ import annotations

from typing import Dict


DEFAULT_LIMITS = {
    "x": 280,
    "threads": 500,
    "linkedin": 3000,
}


def get_limit(config: Dict[str, object], platform: str) -> int:
    limits = config.get("platform_limits", {})
    key = f"{platform}_max_chars"
    return int(limits.get(key, DEFAULT_LIMITS[platform]))


def validate_draft(platform: str, content: str, config: Dict[str, object]) -> Dict[str, object]:
    limit = get_limit(config, platform)
    length = len(content)
    issues = []
    if length > limit:
        issues.append(f"Length {length} exceeds {limit}")
    return {
        "ok": length <= limit,
        "length": length,
        "limit": limit,
        "issues": issues,
        "text": content,
    }


def truncate_to_limit(content: str, limit: int) -> str:
    if len(content) <= limit:
        return content
    if limit <= 3:
        return content[:limit]
    return f"{content[: limit - 3].rstrip()}..."
