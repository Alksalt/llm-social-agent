# src/tools/validation_tools.py

"""
Validation and constraint tools for platform-specific posts.

This module is responsible for:
- Checking hard character limits per platform,
- Returning information about whether a post is valid or too long.

IMPORTANT:
- It does NOT modify or trim the text.
- If a post is too long, it simply reports that fact.
- The orchestrator (higher-level flow) decides what to do next
  (e.g., regenerate with a stricter prompt, or fail and ask user to edit).
"""

from typing import Dict, Any    
from ..core.config_loader import get_config

def _get_platform_limits() -> Dict[str, int]:
    """
    Load character limits for each platform from the YAML config.

    Returns:
        A dict like:
        {
            "x": 240,
            "threads": 300,
            "linkedin": 2000,
        }
    """
    cfg = get_config()
    limits_cfg = cfg.get("platform_limits", {})
    x_limit = int(limits_cfg.get("x_max_chars", 240))
    threads_limit = int(limits_cfg.get("threads_max_chars", 300))
    linkedin_limit = int(limits_cfg.get("linkedin_max_chars", 2000))
    return {
        "x": x_limit,
        "threads": threads_limit,
        "linkedin": linkedin_limit,
    }

def _validate_for_platform(text: str, platform: str) -> Dict[str, Any]:
    """
    Generic validator that checks character limit for a given platform.

    Args:
        text:
            Original text for the post.
        platform:
            Platform key: "x", "threads", or "linkedin".

    Returns:
        A dict with:
        {
            "ok": bool,              # True if text length <= limit
            "length": int,           # Length of the text (after strip)
            "limit": int,            # Allowed character limit
            "text": str,             # The original text (stripped only)
            "error": str | None,     # "too_long" or None
        }
    """

    limits = _get_platform_limits()
    limit = limits[platform]

    cleaned = text.strip()
    length = len(cleaned)

    ok = length <= limit
    error = None if ok else "too_long"
    return {
        "ok": ok,
        "length": length,
        "limit": limit,
        "text": cleaned,
        "error": error,
    }

def validate_x_post(text: str) -> Dict[str, Any]:
    """
    Validate a post for X (Twitter) based on character limit.

    Returns:
        Same structure as _validate_for_platform().
    """
    return _validate_for_platform(text=text, platform="x")


def validate_threads_post(text: str) -> Dict[str, Any]:
    """
    Validate a post for Threads based on character limit.
    """
    return _validate_for_platform(text=text, platform="threads")


def validate_linkedin_post(text: str) -> Dict[str, Any]:
    """
    Validate a post for LinkedIn based on character limit.
    """
    return _validate_for_platform(text=text, platform="linkedin")


