"""Loads STYLE.md contract and optional templates with fallbacks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict

BUILTIN_STYLE_CONTRACT = (
    "Write concise, clear, first-person social posts. Avoid hype, avoid claims you cannot support, "
    "and keep practical value high."
)

BUILTIN_TEMPLATES: Dict[str, str] = {
    "x": (
        "Transform this diary entry into one X post. Keep it punchy and under the platform limit.\n"
        "Diary:\n{entry_text}\n\nSummary:\n{summary}\n\nConstraints:\n{strict_rules}"
    ),
    "threads": (
        "Transform this diary entry into one Threads post. Keep it conversational and concrete.\n"
        "Diary:\n{entry_text}\n\nSummary:\n{summary}\n\nConstraints:\n{strict_rules}"
    ),
    "linkedin": (
        "Transform this diary entry into one LinkedIn post with practical takeaways.\n"
        "Diary:\n{entry_text}\n\nSummary:\n{summary}\n\nConstraints:\n{strict_rules}"
    ),
}


def _parse_markdown_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, str] = {}
    heading_re = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
    matches = list(heading_re.finditer(text))
    if not matches:
        return sections
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        title = match.group(2).strip().lower()
        sections[title] = text[start:end].strip()
    return sections


def load_style(style_path: str) -> Dict[str, object]:
    path = Path(style_path)
    if not path.exists():
        return {
            "exists": False,
            "contract": BUILTIN_STYLE_CONTRACT,
            "templates": dict(BUILTIN_TEMPLATES),
        }

    text = path.read_text(encoding="utf-8")
    sections = _parse_markdown_sections(text)

    contract = text.strip() or BUILTIN_STYLE_CONTRACT
    for title, body in sections.items():
        if "style contract" in title and body.strip():
            contract = body.strip()
            break

    templates = dict(BUILTIN_TEMPLATES)
    for platform in ("x", "threads", "linkedin"):
        for title, body in sections.items():
            if "template" in title and platform in title and body.strip():
                templates[platform] = body.strip()
                break

    return {
        "exists": True,
        "contract": contract,
        "templates": templates,
    }
