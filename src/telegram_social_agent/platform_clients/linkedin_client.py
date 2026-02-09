"""LinkedIn publisher."""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


class LinkedInClient:
    @staticmethod
    def _normalize_person_urn(value: str | None) -> str | None:
        if not value:
            return None
        raw = value.strip()
        if not raw:
            return None
        if raw.startswith("urn:li:person:"):
            return raw
        return f"urn:li:person:{raw}"

    def _resolve_author_urn(self, token: str) -> str | None:
        # Accept either explicit env var.
        explicit = self._normalize_person_urn(os.getenv("LINKEDIN_PERSON_URN"))
        if explicit:
            return explicit
        explicit2 = self._normalize_person_urn(os.getenv("LINKEDIN_PERSON_URN_2"))
        if explicit2:
            return explicit2

        # Fallback: resolve member id from LinkedIn userinfo endpoint.
        res = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        if res.status_code >= 400:
            return None
        data = res.json()
        sub = str(data.get("sub", "")).strip()
        return self._normalize_person_urn(sub)

    def publish(self, content: str, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "platform": "linkedin",
                "simulated_id": "dryrun-linkedin-1",
            }

        token = os.getenv("LINKEDIN_ACCESS_TOKEN")
        author = self._resolve_author_urn(token or "")
        if not token or not author:
            raise RuntimeError(
                "Missing LinkedIn credentials. Set LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN "
                "(or LINKEDIN_PERSON_URN_2), or ensure /v2/userinfo can resolve your member id."
            )

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
        if res.status_code >= 400:
            body = (res.text or "").strip()
            raise RuntimeError(f"LinkedIn publish failed HTTP {res.status_code}: {body[:400]}")
        return {
            "success": True,
            "dry_run": False,
            "platform": "linkedin",
            "response": res.json() if res.text else {},
            "author": author,
        }
