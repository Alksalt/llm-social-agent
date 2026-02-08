"""Publishing helpers and client registry."""

from __future__ import annotations

from typing import Any, Dict

from .platform_clients.linkedin_client import LinkedInClient
from .platform_clients.threads_client import ThreadsClient
from .platform_clients.x_client import XClient


def get_clients() -> Dict[str, Any]:
    return {
        "x": XClient(),
        "threads": ThreadsClient(),
        "linkedin": LinkedInClient(),
    }
