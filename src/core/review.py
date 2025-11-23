# src/core/review.py

"""
Interactive CLI review for newly generated drafts.
"""
from typing import List, Optional, Dict

from .config_loader import get_config
from ..tools.data_tools import get_pending_drafts, set_post_status


def _get_enabled_platforms(cfg: Dict) -> List[str]:
    """
    Return platforms enabled in config in a stable order.
    """
    platforms_cfg = cfg.get("platforms", {})
    enabled = []
    for platform, key in [("x", "x_enabled"), ("threads", "threads_enabled"), ("linkedin", "linkedin_enabled")]:
        if platforms_cfg.get(key, True):
            enabled.append(platform)
    return enabled


def review_drafts_interactive(allowed_diary_ids: Optional[List[int]] = None) -> None:
    """
    Display drafts per enabled platform and ask for y/n approval.
    """
    cfg = get_config()
    enabled_platforms = _get_enabled_platforms(cfg)

    drafts = [
        d for d in get_pending_drafts(allowed_diary_ids=allowed_diary_ids)
        if d["platform"] in enabled_platforms
    ]

    if not drafts:
        print("[Review] No drafts available for enabled platforms.")
        return

    drafts_by_platform: Dict[str, List[dict]] = {}
    for draft in drafts:
        drafts_by_platform.setdefault(draft["platform"], []).append(draft)

    for platform in enabled_platforms:
        platform_drafts = drafts_by_platform.get(platform, [])
        if not platform_drafts:
            continue

        print(f"\n[Review] Platform: {platform}")
        for draft in platform_drafts:
            print(f"\nDraft id={draft['id']} (diary_id={draft['diary_id']}):")
            print(draft["content"])
            answer = input("Approve this draft? (y/n): ").strip().lower()
            if answer == "y":
                set_post_status(draft["id"], "approved")
                print("-> Approved for publishing.")
            else:
                print("-> Left as draft.")
