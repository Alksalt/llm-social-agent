"""X/Twitter publisher."""

from __future__ import annotations

import os
from typing import Any, Dict

import requests
from requests_oauthlib import OAuth1


class XClient:
    def publish(self, content: str, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "platform": "x",
                "simulated_id": "dryrun-x-1",
            }

        api_key = os.getenv("X_API_KEY")
        api_key_secret = os.getenv("X_API_KEY_SECRET")
        access_token = os.getenv("X_ACCESS_TOKEN")
        access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        if not all([api_key, api_key_secret, access_token, access_token_secret]):
            raise RuntimeError("Missing X API credentials")

        auth = OAuth1(api_key, api_key_secret, access_token, access_token_secret)
        res = requests.post(
            "https://api.x.com/2/tweets",
            json={"text": content},
            auth=auth,
            timeout=20,
        )
        res.raise_for_status()
        payload = res.json()
        return {
            "success": True,
            "dry_run": False,
            "platform": "x",
            "response": payload,
        }
