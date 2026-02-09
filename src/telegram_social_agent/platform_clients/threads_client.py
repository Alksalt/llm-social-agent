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

        create_url = f"https://graph.threads.net/v1.0/{user_id}/threads"
        create_res = requests.post(
            create_url,
            data={
                "media_type": "TEXT",
                "text": content,
                "access_token": access_token,
            },
            timeout=20,
        )
        if create_res.status_code >= 400:
            body = (create_res.text or "").strip()
            raise RuntimeError(f"Threads create failed HTTP {create_res.status_code}: {body[:400]}")
        create_payload = create_res.json()
        creation_id = str(create_payload.get("id", "")).strip()
        if not creation_id:
            raise RuntimeError("Threads create did not return creation id")

        publish_url = f"https://graph.threads.net/v1.0/{user_id}/threads_publish"
        publish_res = requests.post(
            publish_url,
            data={
                "creation_id": creation_id,
                "access_token": access_token,
            },
            timeout=20,
        )
        if publish_res.status_code >= 400:
            body = (publish_res.text or "").strip()
            raise RuntimeError(f"Threads publish failed HTTP {publish_res.status_code}: {body[:400]}")
        publish_payload = publish_res.json()

        return {
            "success": True,
            "dry_run": False,
            "platform": "threads",
            "response": {
                "create": create_payload,
                "publish": publish_payload,
            },
        }
