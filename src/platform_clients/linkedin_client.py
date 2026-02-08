"""Thin LinkedIn client used by the publishing pipeline.

Today this module mostly simulates posting (dry-run), but it also includes
the real API call so the portfolio shows how OAuth headers and payloads
are assembled for LinkedIn's UGC endpoint.
"""

import os
from typing import Dict, Any
import requests

from ..core.config_loader import get_config

def _get_linkedin_api_config() -> tuple[str, str, str]:
    """
    Resolve LinkedIn API settings from environment and YAML config.

    Returns:
        base_url, person_urn, access_token strings.
    """
    cfg = get_config()
    linkedin_cfg = cfg.get("linkedin_api", {})
    base_url = linkedin_cfg.get("base_url", "https://api.linkedin.com").rstrip("/")

    access_token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    person_urn = os.getenv("LINKEDIN_PERSON_URN")

    missing = []
    if not access_token:
        missing.append("LINKEDIN_ACCESS_TOKEN")
    if not person_urn:
        missing.append("LINKEDIN_PERSON_URN")

    if missing:
        raise RuntimeError(f"Missing LinkedIn credentials: {', '.join(missing)}")
    return base_url, person_urn, access_token

def publish_linkedin_post(text: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    Publish a post to LinkedIn, or simulate it in dry-run mode.

    Args:
        text:
            Final, validated text for LinkedIn.
        dry_run:
            If True, do NOT call any external API.
            Instead, just print to console and pretend.

    Returns:
        A dict describing the outcome:
        {
            "ok": bool,
            "platform": "linkedin",
            "dry_run": bool,
            "error": None or "some_reason",
            "post_id": None or "placeholder_id",
        }
    """
    platform = "linkedin"
    print("\n[LINKEDIN] Final text to publish:")
    print(text)

    if dry_run:
        print("\n[DRY RUN] Would post to LinkedIn:")
        print(text)
        return {
            "ok": True,
            "platform": platform,
            "dry_run": True,
            "error": None,
            "post_id": None,
        }

    try:
        base_url, person_urn, access_token = _get_linkedin_api_config()
    except RuntimeError as e:
        return {
            "ok": False,
            "platform": platform,
            "dry_run": False,
            "error": f"config_error:{e}",
            "post_id": None,
        }
    url = f"{base_url}/v2/ugcPosts"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0",
    }

    payload = {
        "author": person_urn,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE",
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        },
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
    except requests.RequestException as e:
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
        # LinkedIn returns an entity URN in 'id'
        post_id = None
        if isinstance(data, dict):
            post_id = data.get("id")

        print(f"[LINKEDIN] Successfully posted. Status={status}, id={post_id}")
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
        if "message" in data:
            error_message = f"{error_message}:{data['message']}"
        else:
            error_message = f"{error_message}:{data}"
    else:
        error_message = f"{error_message}:{resp.text[:500]}"

    print(f"[LINKEDIN] Failed to post. {error_message}")
    return {
        "ok": False,
        "platform": platform,
        "dry_run": False,
        "error": error_message,
        "post_id": None,
    }
