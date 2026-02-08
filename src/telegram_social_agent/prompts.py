"""Prompt builders."""

from __future__ import annotations

from typing import Dict


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def build_summary_prompt(entry_text: str) -> str:
    return (
        "Summarize this diary entry in 2-3 sentences. "
        "Preserve concrete facts, remove fluff, and do not invent details.\n\n"
        f"Diary entry:\n{entry_text}"
    )


def build_draft_prompt(
    platform: str,
    entry_text: str,
    summary: str,
    style_template: str,
    is_strict: bool,
    limit: int,
) -> str:
    strict_rules = (
        f"Hard limit: {limit} chars. Use conservative wording, no risky claims."
        if is_strict
        else f"Hard limit: {limit} chars. Keep tone natural and practical."
    )
    vars_map = _SafeDict(
        entry_text=entry_text,
        summary=summary,
        strict_rules=strict_rules,
        platform=platform,
        char_limit=limit,
    )
    return style_template.format_map(vars_map)


def build_system_prompt(style_contract: str) -> str:
    return (
        "You are a social writing assistant. Follow this style contract exactly when possible:\n\n"
        f"{style_contract}"
    )
