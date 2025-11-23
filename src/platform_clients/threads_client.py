# src/platform_clients/threads_client.py

"""
Client for posting content to Threads.

CURRENT STATUS:
- Dry-run only: does NOT call the real Threads API.
- Prints what it *would* post and returns a structured result.

LATER:
- We'll integrate with Meta's Threads API via the Graph API,
  once app + tokens are in place.
"""

import os
from typing import Dict, Any
import requests

from ..core.config_loader import get_config


def _get_threads_api_config() -> tuple[str, str, str]:
    """
    Returns:
        (base_url, user_id, access_token)
    """
    cfg = get_config()
    threads_cfg = cfg.get("threads_api", {})
    base_url = threads_cfg.get("base_url", "https://graph.threads.net").rstrip("/")

    user_id = os.getenv("THREADS_USER_ID")
    access_token = os.getenv("THREADS_ACCESS_TOKEN")

    missing = []
    if not user_id:
        missing.append("THREADS_USER_ID")
    if not access_token:
        missing.append("THREADS_ACCESS_TOKEN")

    if missing:
        raise RuntimeError(f"Missing Threads credentials: {', '.join(missing)}")

    return base_url, user_id, access_token

def publish_threads_post(text: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Publish a text post to Threads.

    If dry_run=True: print and return ok=True
    If dry_run=False: call POST /{USER_ID}/threads
    """
    platform = "threads"

    print("\n[THREADS] Final text to publish:")
    print(text)

    if dry_run:
        print("[THREADS] DRY RUN: not calling Threads API.")
        return {
            "ok": True,
            "platform": platform,
            "dry_run": True,
            "error": None,
            "post_id": None,
        }

    try:
        base_url, user_id, access_token = _get_threads_api_config()
    except RuntimeError as e:
        print(f"[THREADS] Config error: {e}")
        return {
            "ok": False,
            "platform": platform,
            "dry_run": False,
            "error": f"config_error:{e}",
            "post_id": None,
        }
    url = f"{base_url}/{user_id}/threads"

    params = {
        "text": text,
        "media_type": "TEXT",
        "auto_publish_text": "true",
        "access_token": access_token,
    }

    try:
        resp = requests.post(url, params=params, timeout=10)
    except requests.RequestException as e:
        print(f"[THREADS] Network error: {e}")
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
    except:
        data = None

    if 200 <= status < 300:
        post_id = data.get("id") if isinstance(data, dict) else None
        print(f"[THREADS] Successfully posted. Status={status}, id={post_id}")
        return {
            "ok": True,
            "platform": platform,
            "dry_run": False,
            "error": None,
            "post_id": post_id,
        }
    error_message = f"status_{status}"
    if isinstance(data, dict):
        if "error" in data and "message" in data["error"]:
            error_message = f"{error_message}:{data['error']['message']}"
        else:
            error_message = f"{error_message}:{data}"
    else:
        error_message = f"{error_message}:{resp.text[:500]}"

    print(f"[THREADS] Failed to post. {error_message}")

    return {
        "ok": False,
        "platform": platform,
        "dry_run": False,
        "error": error_message,
        "post_id": None,
    }
