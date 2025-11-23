# src/core/publisher.py

"""
Publishing pipeline.

This module is responsible for:
- Selecting pending drafts from the database,
- Re-validating length per platform,
- Enforcing LinkedIn weekly posting limits,
- Calling platform clients in dry-run or real mode,
- Logging publish results and marking posts as published.

It does NOT generate content; that is handled by the orchestrator.
"""

from typing import Dict, Any, List, Optional

from ..core.config_loader import get_config
from ..tools.validation_tools import (
    validate_x_post,
    validate_threads_post,
    validate_linkedin_post,
)
from ..tools.data_tools import (
    get_approved_posts,
    mark_post_as_published,
    log_publish_result,
    count_linkedin_publishes_last_days,
)
from ..platform_clients.x_client import publish_x_post
from ..platform_clients.threads_client import publish_threads_post
from ..platform_clients.linkedin_client import publish_linkedin_post

def _validate_for_platform(platform: str, text: str) -> Dict[str, Any]:
    """
    Route to the correct validation function per platform.

    Args:
        platform:
            'x', 'threads', or 'linkedin'.
        text:
            Post content to validate.

    Returns:
        Validation dict (see validation_tools) or a fake error for unknown platform.
    """
    platform = platform.lower().strip()

    if platform == "x":
        return validate_x_post(text)
    if platform == "threads":
        return validate_threads_post(text)
    if platform == "linkedin":
        return validate_linkedin_post(text)

    # Unknown platform: treat as invalid
    return {
        "ok": False,
        "length": len(text.strip()),
        "limit": 0,
        "text": text.strip(),
        "error": f"unsupported_platform:{platform}",
    }

def _publish_to_platform(platform: str, text: str, dry_run: bool) -> Dict[str, Any]:
    """
    Route to the correct platform client.

    Args:
        platform:
            'x', 'threads', or 'linkedin'.
        text:
            Post content to publish.
        dry_run:
            If True, clients will only simulate posting.

    Returns:
        Dict from the platform client (see platform_clients/*_client.py).
    """
    platform = platform.lower().strip()

    if platform == "x":
        return publish_x_post(text, dry_run=dry_run)
    if platform == "threads":
        return publish_threads_post(text, dry_run=dry_run)
    if platform == "linkedin":
        return publish_linkedin_post(text, dry_run=dry_run)

    return {
        "ok": False,
        "platform": platform,
        "dry_run": dry_run,
        "error": f"unsupported_platform:{platform}",
        "post_id": None,
    }

def run_publishing_pipeline(allowed_diary_ids: Optional[List[int]] = None) -> None:
    """
    Main function to publish APPROVED posts.

    Steps:
    - Load config (dry_run flag, platform enable flags, LinkedIn weekly cap),
    - Fetch all posts with status='approved' (optionally filtered by diary_ids),
    - For each post:
        - Skip if platform disabled,
        - Validate length (no trimming),
        - Enforce LinkedIn weekly limit,
        - Call platform client (dry-run or real),
        - Log result in publish_logs,
        - Mark post as 'published' if ok.

    Notes:
    - This function does NOT handle regeneration for too-long posts.
      If a post is too long, we log a failed publish and keep status='approved'
      so you can fix or regenerate it later.
    """
    cfg = get_config()
    modes_cfg = cfg.get("modes", {})
    platforms_cfg = cfg.get("platforms", {})
    posting_limits_cfg = cfg.get("posting_limits", {})

    dry_run = bool(modes_cfg.get("dry_run", True))
    linkedin_weekly_cap = int(posting_limits_cfg.get("linkedin_per_week", 3))
    platform_enabled = {
        "x": bool(platforms_cfg.get("x_enabled", True)),
        "threads": bool(platforms_cfg.get("threads_enabled", True)),
        "linkedin": bool(platforms_cfg.get("linkedin_enabled", True)),
    }

    # How many successful LinkedIn publishes happened in last 7 days
    linkedin_count = count_linkedin_publishes_last_days(days=7)

    print(f"\n[Publishing] dry_run={dry_run}")
    print(f"[Publishing] LinkedIn posts last 7 days: {linkedin_count}/{linkedin_weekly_cap}")

    posts_to_publish = [
        p for p in get_approved_posts(allowed_diary_ids=allowed_diary_ids)
        if platform_enabled.get(p["platform"], False)
    ]

    if not posts_to_publish:
        print("[Publishing] No posts with status='approved'. Nothing to do.")
        return

    for post in posts_to_publish:
        post_id = post["id"]
        platform = post["platform"]
        content = post["content"]

        # LinkedIn weekly cap
        if platform == "linkedin":
            if linkedin_count >= linkedin_weekly_cap:
                print(
                    f"[Publishing] LinkedIn weekly cap reached "
                    f"({linkedin_count}/{linkedin_weekly_cap}), skipping post_id={post_id}."
                )
                # Keep status='approved' for later
                continue

        # Length validation per platform (no trimming)
        validation = _validate_for_platform(platform, content)

        if not validation["ok"]:
            print(
                f"[Publishing] Post_id={post_id} ({platform}) is too long or invalid "
                f"({validation['length']}/{validation['limit']}). Skipping publish."
            )
            # Log failed attempt due to validation error
            log_publish_result(
                post_id=post_id,
                platform=platform,
                success=False,
                api_response_excerpt=f"validation_error:{validation.get('error', 'too_long')}",
            )
            # Status stays 'approved'; you can later edit/regen it.
            continue

        # Call platform client (dry-run or real)
        client_result = _publish_to_platform(
            platform=platform,
            text=validation["text"],  # already stripped, validated text
            dry_run=dry_run,
        )

        # Log result in publish_logs
        log_publish_result(
            post_id=post_id,
            platform=platform,
            success=client_result["ok"],
            api_response_excerpt=str(client_result.get("error")),
        )

        if client_result["ok"]:
            # Mark as 'published' in posts table
            mark_post_as_published(post_id)
            print(
                f"[Publishing] Successfully {'simulated ' if dry_run else ''}publish "
                f"for post_id={post_id} on {platform}."
            )

            if platform == "linkedin":
                linkedin_count += 1
        else:
            print(
                f"[Publishing] Failed to publish post_id={post_id} on {platform}. "
                f"Error: {client_result.get('error')}"
            )
