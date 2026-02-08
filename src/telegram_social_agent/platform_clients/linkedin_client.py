"""LinkedIn publisher."""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


class LinkedInClient:
    def publish(self, content: str, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "platform": "linkedin",
                "simulated_id": "dryrun-linkedin-1",
            }

        token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        author = os.getenv("LINKEDIN_PERSON_URN")
        if not token or not author:
            raise RuntimeError("Missing LinkedIn credentials")

        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        res = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
            },
            timeout=20,
        )
        res.raise_for_status()
        return {
            "success": True,
            "dry_run": False,
            "platform": "linkedin",
            "response": res.json() if res.text else {},
        }
