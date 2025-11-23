# src/tools/content_tools.py

"""
Content-related tools.

These functions are responsible for:
- Summarizing the raw diary text.
- Generating platform-specific drafts (X, Threads, LinkedIn)
  from the diary and summary.

They use the core LLM client (`generate_text`) instead of talking
to the OpenAI SDK directly. This keeps the rest of the codebase clean.
"""

from typing import Dict, Any
from ..core.llm_client import generate_text
from ..core.config_loader import get_config

def summarize_diary(diary_text: str) -> str: 
    """
    Produce a short summary of the diary entry.

    This summary is:
    - Human-readable (you can show it in a UI),
    - Also used as a compact context for generating posts.

    Args:
        diary_text: The raw diary-style note written by the user.

    Returns:
        A short summary string.
    """
    system_prompt = (
        "You are an assistant that helps summarize a daily diary "
        "about someone's journey learning LLMs and agentic AI."
        "Write concise, clear summaries without adding fictitious details."
    )

    user_prompt = (
        "You will be given a diary entry written in an informal style.\n"
        "Task:\n"
        "- Summarize it in 2–4 sentences.\n"
        "- Focus on what was done, what was learned, and any blockers.\n"
        "- Do NOT add anything that isn't in the diary.\n\n"
        f"Diary entry:\n{diary_text}"
    )
    summary = generate_text(prompt=user_prompt, system_prompt=system_prompt)
    return summary.strip()

def generate_x_post_from_diary(diary_text: str, summary: str) -> Dict[str,str]:
    """
    Generate a draft X (Twitter) post from the diary and its summary.

    Args:
        diary_text:
            Original diary text (can give extra nuance if needed).
        summary:
            Short summary of the diary (used as compact context).

    Returns:
        A dict with at least:
        {
            "text": "<post text>",
            "notes": "<optional explanation or reasoning>"
        }
    """
    system_prompt = (
        "You document your AI grind on X like a feral developer with Wi-Fi. "
        "Tone: sharp, sarcastic, unapologetically honest, occasionally dark. "
        "No motivational nonsense, no cringe hustle-talk. "
        "You're new here, so you overshare your tech wins and fails with deadpan humor. "
        "Audience: devs, AI weirdos, recruiters with high tolerance for chaos."
    )

    user_prompt = (
        "From the chaos-log below, craft ONE X post.\n"
        "Rules:\n"
        "- Max ~240 chars. If it’s longer, I’ll amputate it.\n"
        "- Focus on ONE idea from today — the one that didn’t bore me to death.\n"
        "- It must make sense without any backstory.\n"
        "- Optional: 0–2 hashtags if they actually add value.\n\n"
        f"Diary summary:\n{summary}\n\n"
        "Output ONLY the post text. No disclaimers. No fluff."
    )
    post_text = generate_text(prompt=user_prompt, system_prompt=system_prompt)
    return {
        "text": post_text.strip(),
        "notes": "Generated from diary summary for X. Hard character limit will be checked later.",
    }

def generate_threads_post_from_diary(diary_text: str, summary: str) -> Dict[str, str]:
    """
    Generate a draft Threads post from the diary and its summary.

    Args:
        diary_text:
            Original diary text.
        summary:
            Short summary of the diary.

    Returns:
        A dict with:
        {
            "text": "<post text>",
            "notes": "<optional explanation or reasoning>"
        }
    """
    system_prompt = (
        "You help a developer reflect on their LLM and agentic AI journey on Threads. "
        "Tone: chill, sincere, a bit humorous — like talking to someone on a coffee break. "
        "Keep it human, not polished. No hustle culture, no try-hard vibes."
    )
    user_prompt = (
        "Using the reflection below, write ONE Threads post.\n\n"
        "Guidelines:\n"
        "- Keep it relaxed and personal — more like sharing a moment than performing.\n"
        "- Slightly longer than a tweet is fine, as long as it fits comfortably on one screen.\n"
        "- Capture one clear thought from today’s learning so it feels like a genuine journey.\n"
        "- Emojis are allowed, but only if they feel natural.\n\n"
        f"Diary summary:\n{summary}\n\n"
        "Output ONLY the post text. No commentary, no formatting."
    )
    post_text = generate_text(prompt=user_prompt, system_prompt=system_prompt)

    return {
        "text": post_text.strip(),
        "notes": "Generated from diary summary for Threads. Validation will handle length later.",
    }
def generate_linkedin_post_from_diary(diary_text: str, summary: str) -> Dict[str, str]:
    """
    Generate a draft LinkedIn post from the diary and its summary.

    Args:
        diary_text:
            Original diary text.
        summary:
            Short summary used as high-level context.

    Returns:
        A dict with:
        {
            "text": "<post text>",
            "notes": "<optional explanation or reasoning>"
        }
    """
    system_prompt = (
        "You help a professional share their learning journey in LLMs and agentic AI on LinkedIn. "
        "Tone: clear, grounded, reflective, professionally confident without corporate jargon. "
        "Audience: tech peers, hiring managers, and curious learners. "
        "Focus on insight and clarity, not hype."
    )
    user_prompt = (
        "Using the summary below, write a LinkedIn post.\n\n"
        "Structure:\n"
        "1) A concise opening that highlights today’s main focus.\n"
        "2) 2–4 short, readable paragraphs on what you explored, built, or realized.\n"
        "3) A closing line that reflects on the learning journey or points toward the next step.\n\n"
        "Guidelines:\n"
        "- Keep the language clear and grounded; explain any technical terms briefly.\n"
        "- Focus on genuine progress—small wins and challenges are both valuable.\n"
        "- Make the post understandable to readers who follow AI but aren’t deep in ML.\n\n"
        f"Diary summary:\n{summary}\n\n"
        "Output the full LinkedIn post text only, without additional commentary."
    )
    post_text = generate_text(prompt=user_prompt, system_prompt=system_prompt)

    return {
        "text": post_text.strip(),
        "notes": "Generated from diary summary for LinkedIn with a structured narrative.",
    }

def generate_post_variants(diary_text: str) -> Dict[str, Any]:
    """
    High-level helper to go from raw diary text to all platform-specific drafts.

    This function coordinates:
    - Summarizing the diary,
    - Generating X, Threads, and LinkedIn drafts from that summary.

    Args:
        diary_text:
            Raw diary text written by the user (one day's entry).

    Returns:
        A dict with the structure:
        {
            "summary": "<summary>",
            "x": {"text": "...", "notes": "..."},
            "threads": {"text": "...", "notes": "..."},
            "linkedin": {"text": "...", "notes": "..."}
        }
    """
    summary = summarize_diary(diary_text)

    x_post = generate_x_post_from_diary(diary_text=diary_text, summary=summary)
    threads_post = generate_threads_post_from_diary(diary_text=diary_text, summary=summary)
    linkedin_post = generate_linkedin_post_from_diary(diary_text=diary_text, summary=summary)
    drafts = {
        "summary": summary,
        "x": x_post,
        "threads": threads_post,
        "linkedin": linkedin_post,
    }

    return drafts

def _get_platform_limits() -> Dict[str, int]:
    """
    Load character limits for each platform from config.

    This is a small helper used for regeneration prompts
    so the model knows the target max length.
    """
    cfg = get_config()
    limits_cfg = cfg.get("platform_limits", {})

    x_limit = int(limits_cfg.get("x_max_chars", 240))
    threads_limit = int(limits_cfg.get("threads_max_chars", 300))
    linkedin_limit = int(limits_cfg.get("linkedin_max_chars", 2000))

    return {
        "x": x_limit,
        "threads": threads_limit,
        "linkedin": linkedin_limit,
    }

def regenerate_x_post_more_concise(
    summary: str,
    previous_text: str,
) -> Dict[str, str]:
    """
    Regenerate an X post that was too long, forcing higher conciseness.

    We use:
    - The diary summary as context,
    - The previous (too long) text as a reference for the idea,
    - A stricter instruction with an explicit character limit.
    """
    limits = _get_platform_limits()
    max_chars = limits["x"]

    system_prompt = (
        "You are helping a developer share their daily progress "
        "learning and building with LLMs and agentic AI on X (Twitter).\n"
        "Tone: honest, concise, slightly nerdy, no fake hype."
    )

    user_prompt = (
        "You previously wrote an X post that was too long.\n"
        "Now rewrite the SAME core idea in a much more concise way.\n\n"
        f"Target:\n"
        f"- ABSOLUTE hard limit: {max_chars} characters (including spaces).\n"
        f"- Prefer closer to {max_chars - 20} characters to be safe.\n\n"
        "Constraints:\n"
        "- Keep only one main idea or lesson.\n"
        "- Make every word earn its place.\n"
        "- It's okay to drop details; focus on the core.\n"
        "- Optional: 0–1 hashtags.\n\n"
        "Diary summary:\n"
        f"{summary}\n\n"
        "Previous (too long) X draft:\n"
        f"{previous_text}\n\n"
        "Now WRITE ONLY the new, shorter X post text."
    )

    new_text = generate_text(prompt=user_prompt, system_prompt=system_prompt)

    return {
        "text": new_text.strip(),
        "notes": "Regenerated for conciseness after initial X draft was too long.",
    }

def regenerate_threads_post_more_concise(
    summary: str,
    previous_text: str,
) -> Dict[str, str]:
    """
    Regenerate a Threads post that was too long, keeping it relaxed but shorter.
    """
    limits = _get_platform_limits()
    max_chars = limits["threads"]

    system_prompt = (
        "You help a developer share their daily LLM/agentic AI journey on Threads.\n"
        "Tone: relaxed, personal, authentic; avoid being overly formal."
    )

    user_prompt = (
        "You previously wrote a Threads post that was too long.\n"
        "Now rewrite the SAME idea more concisely while keeping a personal tone.\n\n"
        f"Target:\n"
        f"- Hard limit: {max_chars} characters.\n"
        f"- Aim for something shorter than that so it definitely fits.\n\n"
        "Constraints:\n"
        "- 1–3 short sentences or a compact mini-paragraph.\n"
        "- Light, human tone is more important than detail.\n"
        "- Emojis allowed but keep them minimal.\n\n"
        "Diary summary:\n"
        f"{summary}\n\n"
        "Previous (too long) Threads draft:\n"
        f"{previous_text}\n\n"
        "Now WRITE ONLY the new, shorter Threads post text."
    )

    new_text = generate_text(prompt=user_prompt, system_prompt=system_prompt)

    return {
        "text": new_text.strip(),
        "notes": "Regenerated for conciseness after initial Threads draft was too long.",
    }

def regenerate_linkedin_post_more_concise(
    summary: str,
    previous_text: str,
) -> Dict[str, str]:
    """
    Regenerate a LinkedIn post that was too long, keeping a clear structure
    but compressing the content.
    """
    limits = _get_platform_limits()
    max_chars = limits["linkedin"]

    system_prompt = (
        "You help a professional share their learning journey in LLMs and agentic AI on LinkedIn.\n"
        "Tone: clear, reflective, professional but human."
    )

    user_prompt = (
        "You previously wrote a LinkedIn post that was too long.\n"
        "Now rewrite the SAME post idea in a more compact way.\n\n"
        f"Target:\n"
        f"- Hard limit: {max_chars} characters.\n"
        f"- Aim significantly under the limit for safety.\n\n"
        "Constraints:\n"
        "- Keep a very short hook.\n"
        "- 1–2 short paragraphs max.\n"
        "- Keep one main insight or lesson.\n"
        "- Cut side stories and minor details.\n\n"
        "Diary summary:\n"
        f"{summary}\n\n"
        "Previous (too long) LinkedIn draft:\n"
        f"{previous_text}\n\n"
        "Now WRITE ONLY the new, shorter LinkedIn post text."
    )

    new_text = generate_text(prompt=user_prompt, system_prompt=system_prompt)

    return {
        "text": new_text.strip(),
        "notes": "Regenerated for conciseness after initial LinkedIn draft was too long.",
    }

