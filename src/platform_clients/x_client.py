# src/platform_clients/x_client.py

"""
Client for posting content to X (Twitter).

CURRENT BEHAVIOR:
- If dry_run=True: just prints what it would post.
- If dry_run=False: uses OAuth 1.0a user context with:
    X_API_KEY
    X_API_KEY_SECRET
    X_ACCESS_TOKEN
    X_ACCESS_TOKEN_SECRET
to call POST /2/tweets.
"""

import os
from typing import Dict, Any

import requests
from requests_oauthlib import OAuth1
from ..core.config_loader import get_config

def _get_x_oauth1_config() -> tuple[str, OAuth1]:
    """
    Build OAuth1 auth object and base URL for X API.

    Uses environment variables:
    - X_API_KEY
    - X_API_KEY_SECRET
    - X_ACCESS_TOKEN
    - X_ACCESS_TOKEN_SECRET

    Returns:
        (base_url, oauth1_auth)

    Raises:
        RuntimeError if any required env var is missing.
    """
    cfg = get_config()
    x_cfg = cfg.get("x_api", {})
    base_url = x_cfg.get("base_url", "https://api.x.com").rstrip("/")

    api_key = os.getenv("X_API_KEY")
    api_secret = os.getenv("X_API_KEY_SECRET")
    access_token = os.getenv("X_ACCESS_TOKEN")
    access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")

    missing = [
        name
        for name, value in [
            ("X_API_KEY", api_key),
            ("X_API_KEY_SECRET", api_secret),
            ("X_ACCESS_TOKEN", access_token),
            ("X_ACCESS_TOKEN_SECRET", access_token_secret),
        ]
        if not value
    ]

    if missing:
        raise RuntimeError(
            f"Missing X OAuth credentials in environment: {', '.join(missing)}"
        )

    oauth = OAuth1(
        api_key,            # consumer_key
        api_secret,         # consumer_secret
        access_token,       # resource_owner_key
        access_token_secret # resource_owner_secret
    )

    return base_url, oauth


def publish_x_post(text: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Publish a post to X (Twitter), or simulate it in dry-run mode.

    Args:
        text:
            Final, validated text for X.
        dry_run:
            If True: do NOT call X API, only print.
            If False: call POST /2/tweets using OAuth 1.0a user context.

    Returns:
        {
            "ok": bool,
            "platform": "x",
            "dry_run": bool,
            "error": None or "error_message",
            "post_id": None or "remote_id",
        }
    """
    platform = "x"
    if dry_run:
        print("\n[DRY RUN] Would post to X:")
        print(text)
        return {
                "ok": True,
                "platform": platform,
                "dry_run": True,
                "error": None,
                "post_id": None,
            }
    # 3) Real call: load base_url + bearer from config/env
    try:
        base_url, oauth = _get_x_oauth1_config()
    except RuntimeError as e:
        print(f"[X] Config error: {e}")
        return {
            "ok": False,
            "platform": platform,
            "dry_run": False,
            "error": f"config_error:{e}",
            "post_id": None,
        }

    url = f"{base_url}/2/tweets"
    payload = {"text": text}

    try:
        resp = requests.post(url, json=payload, auth=oauth, timeout=10)
    except requests.RequestException as e:
        print(f"[X] Network error while calling X API: {e}")
        return {
            "ok": False,
            "platform": platform,
            "dry_run": False,
            "error": f"network_error:{e}",
            "post_id": None,
        }

    status = resp.status_code

    try:
        data = resp.json()
    except ValueError:
        data = None

    if 200 <= status < 300:
        post_id = None
        if isinstance(data, dict):
            post_id = (data.get("data") or {}).get("id")
        print(f"[X] Successfully posted tweet. Status={status}, id={post_id}")
        return {
            "ok": True,
            "platform": platform,
            "dry_run": False,
            "error": None,
            "post_id": post_id,
        }

    # Error
    error_message = f"status_{status}"
    if isinstance(data, dict):
        detail = data.get("detail") or data.get("title") or str(data)
        error_message = f"{error_message}:{detail}"
    else:
        error_message = f"{error_message}:{resp.text[:500]}"

    print(f"[X] Failed to post tweet. {error_message}")
    return {
        "ok": False,
        "platform": platform,
        "dry_run": False,
        "error": error_message,
        "post_id": None,
    }