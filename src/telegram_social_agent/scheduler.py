"""Scheduler runner for due drafts."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Dict

from .orchestrator import run_scheduler_once
from .publishing import get_clients


def run_due_scheduler(conn, config: Dict[str, Any]) -> Dict[str, Any]:
    timezone_name = config.get("timezone", "Europe/Oslo")
    now_local = datetime.now(ZoneInfo(timezone_name))
    now_iso = now_local.astimezone(ZoneInfo("UTC")).isoformat()
    return run_scheduler_once(conn, config, now_iso=now_iso, clients=get_clients())
