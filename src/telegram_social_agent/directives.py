"""Directive parsing for hashtags and command platform lists."""

from __future__ import annotations

from typing import Dict, List

VALID_PLATFORMS = {"x", "threads", "linkedin"}
ALIASES = {
    "twitter": "x",
    "thread": "threads",
    "li": "linkedin",
}


def normalize_platform(token: str) -> str | None:
    clean = token.strip().lower().rstrip(",")
    clean = ALIASES.get(clean, clean)
    if clean in VALID_PLATFORMS:
        return clean
    return None


def parse_platform_args(args: List[str], default_platforms: List[str]) -> List[str]:
    if not args:
        return default_platforms
    parsed: List[str] = []
    for arg in args:
        platform = normalize_platform(arg)
        if platform and platform not in parsed:
            parsed.append(platform)
    return parsed or default_platforms


def parse_directives(text: str) -> Dict[str, object]:
    tokens = text.split()
    kept_tokens: List[str] = []
    wants_draft = False
    wants_publish = False
    is_private = False
    is_strict = False
    publish_platforms: List[str] = []

    i = 0
    while i < len(tokens):
        token = tokens[i]
        lower = token.lower()

        if lower == "#draft":
            wants_draft = True
            i += 1
            continue
        if lower == "#private":
            is_private = True
            i += 1
            continue
        if lower == "#strict":
            is_strict = True
            i += 1
            continue
        if lower == "#publish":
            wants_publish = True
            i += 1
            while i < len(tokens):
                platform = normalize_platform(tokens[i])
                if not platform:
                    break
                if platform not in publish_platforms:
                    publish_platforms.append(platform)
                i += 1
            continue

        kept_tokens.append(token)
        i += 1

    cleaned_text = " ".join(kept_tokens).strip()

    return {
        "cleaned_text": cleaned_text,
        "flags": {
            "private": is_private,
            "strict": is_strict,
            "draft": wants_draft,
            "publish": wants_publish,
            "publish_platforms": publish_platforms,
        },
    }
