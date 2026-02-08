"""Threads publisher."""

from __future__ import annotations

import os
from typing import Any, Dict

import requests


class ThreadsClient:
    def publish(self, content: str, dry_run: bool = True) -> Dict[str, Any]:
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "platform": "threads",
                "simulated_id": "dryrun-threads-1",
            }

        user_id = os.getenv("THREADS_USER_ID")
        access_token = os.getenv("THREADS_ACCESS_TOKEN")
        if not user_id or not access_token:
            raise RuntimeError("Missing Threads credentials")

        url = f"https://graph.threads.net/v1.0/{user_id}/threads"
        res = requests.post(
            url,
            data={"text": content, "access_token": access_token},
            timeout=20,
        )
        res.raise_for_status()
        payload = res.json()
        return {
            "success": True,
            "dry_run": False,
            "platform": "threads",
            "response": payload,
        }
