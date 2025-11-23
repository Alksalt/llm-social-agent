# src/core/orchestrator.py

"""
Orchestrator ("agent brain") for the diary -> drafts pipeline.

This module coordinates:
- Checking if a diary entry is new,
- Storing the diary,
- Summarizing the diary,
- Generating platform-specific drafts,
- Validating character limits (without trimming),
- Storing drafts in the database.

Right now it's a clean, deterministic pipeline: one diary text in, structured result out.
"""
from typing import Dict, Any

from ..tools.data_tools import (
    is_new_diary_entry,
    store_diary_entry,
    store_post_draft,
)
from ..tools.content_tools import (
    summarize_diary,
    generate_x_post_from_diary,
    generate_threads_post_from_diary,
    generate_linkedin_post_from_diary,
    regenerate_x_post_more_concise,
    regenerate_threads_post_more_concise,
    regenerate_linkedin_post_more_concise,
)
from ..tools.validation_tools import (
    validate_x_post,
    validate_threads_post,
    validate_linkedin_post,
)
from ..core.config_loader import get_config

_VALIDATORS = {
    "x": validate_x_post,
    "threads": validate_threads_post,
    "linkedin": validate_linkedin_post,
}


def _generate_and_validate(
    platform: str,
    diary_text: str,
    summary: str,
) -> tuple[dict, dict]:
    """
    Generate a draft for a platform and validate/regenerate it once if too long.
    """
    generators = {
        "x": generate_x_post_from_diary,
        "threads": generate_threads_post_from_diary,
        "linkedin": generate_linkedin_post_from_diary,
    }
    validators = {
        "x": validate_x_post,
        "threads": validate_threads_post,
        "linkedin": validate_linkedin_post,
    }
    regenerators = {
        "x": regenerate_x_post_more_concise,
        "threads": regenerate_threads_post_more_concise,
        "linkedin": regenerate_linkedin_post_more_concise,
    }

    draft = generators[platform](diary_text=diary_text, summary=summary)
    validation = validators[platform](draft["text"])
    if not validation["ok"]:
        draft = regenerators[platform](summary=summary, previous_text=draft["text"])
        validation = validators[platform](draft["text"])
    return draft, validation


def process_diary_text(diary_text: str, source: str = "diary_file") -> Dict[str, Any]:
    """
    High-level pipeline for handling a single diary text or prewritten post.

    With llm_enabled=True (default):
    - Clean and sanity-check the text,
    - Deduplicate,
    - Store diary in DB,
    - Summarize via LLM,
    - Generate drafts for X, Threads, LinkedIn,
    - Validate each draft's length (no trimming),
    - Store drafts as 'draft' posts in DB.

    With llm_enabled=False:
    - Clean and sanity-check the text,
    - Deduplicate,
    - Store diary in DB,
    - Skip LLM calls; reuse the raw text for each enabled platform,
    - Validate length (no regeneration),
    - Store drafts as 'draft' posts in DB.

    Args:
        diary_text:
            Raw diary text written by the user.
        source:
            Label indicating where this diary came from.
            For now: usually 'diary_file'.
            Later: we will also use 'x_threads_file'.

    Returns:
        A dict describing what happened, for example:
        {
            "ok": True,
            "reason": None,
            "diary_id": 1,
            "summary": "...",
            "posts": {
                "x": {
                    "post_id": 10,
                    "content": "...",
                    "validation": { ... }
                },
                "threads": { ... },
                "linkedin": { ... }
            }
        }

        If the diary is empty or duplicate, ok will be False and reason will say why.
    """
    cfg = get_config()
    modes_cfg = cfg.get("modes", {})
    platform_cfg = cfg.get("platforms", {})
    llm_enabled = bool(modes_cfg.get("llm_enabled", True))
    platform_enabled = {
        "x": bool(platform_cfg.get("x_enabled", True)),
        "threads": bool(platform_cfg.get("threads_enabled", True)),
        "linkedin": bool(platform_cfg.get("linkedin_enabled", True)),
    }

    # 1) Basic cleanup and empty check
    cleaned_diary = diary_text.strip()
    if not cleaned_diary:
        return {
            "ok": False,
            "reason": "empty_diary",
            "diary_id": None,
            "summary": None,
            "posts": {},
        }
    if not is_new_diary_entry(cleaned_diary, source=source):
        return {
            "ok": False,
            "reason": "duplicate_diary",
            "diary_id": None,
            "summary": None,
            "posts": {}
        }
    # 3) Store diary entry in DB
    diary_id = store_diary_entry(cleaned_diary, source=source)

    # 4) Summarize the diary or pass through raw text when LLM is off
    summary = summarize_diary(cleaned_diary) if llm_enabled else cleaned_diary
    posts_result: Dict[str, Any] = {}

    requested_platforms = ["x", "threads"] if source == "x_threads_file" else ["x", "threads", "linkedin"]
    active_platforms = [p for p in requested_platforms if platform_enabled.get(p, False)]

    for platform in active_platforms:
        if llm_enabled:
            draft, validation = _generate_and_validate(platform, cleaned_diary, summary)
        else:
            validation = _VALIDATORS[platform](cleaned_diary)
            draft = {
                "text": validation["text"],
                "notes": "LLM disabled; using raw input text for this platform.",
            }
        post_id = store_post_draft(diary_id, platform, draft["text"], status="draft")
        posts_result[platform] = {
            "post_id": post_id,
            "content": draft["text"],
            "notes": draft.get("notes"),
            "validation": validation,
        }

    # Final result
    return {
        "ok": True,
        "reason": None,
        "diary_id": diary_id,
        "summary": summary,
        "posts": posts_result,
    }
