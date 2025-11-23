"""CLI entrypoint for the social diary agent pipeline."""

from .db.models import init_db
from .core.config_loader import get_config
from .core.orchestrator import process_diary_text
from .core.publisher import run_publishing_pipeline
from .core.review import review_drafts_interactive
from .tools.file_tools import read_text_file


def _run_for_source(text: str, source: str):
    """
    Runs the orchestrator for a given text/file source
    and RETURNS the orchestrator result dict so that main() can collect diary_ids.

    Returns:
        result dict or None if skipped.
    """
    cleaned = text.strip()

    if not cleaned:
        print(f"[{source}] No text found (empty file or only whitespace). Skipping.")
        return None

    result = process_diary_text(cleaned, source=source)

    if not result["ok"]:
        print(f"[{source}] Pipeline skipped. Reason: {result['reason']}")
        return None

    print(f"[{source}] Diary stored with id={result['diary_id']}")
    print(f"[{source}] Summary:\n{result['summary']}")

    for platform, info in result["posts"].items():
        v = info["validation"]
        status = "OK" if v["ok"] else f"TOO LONG ({v['length']}/{v['limit']})"
        print(f"\n[{source}] --- {platform.upper()} ---")
        print("Validation:", status)
        print(info["content"])

    return result


def main() -> None:
    """
    Final orchestrator:
    1. Load config
    2. Generate drafts (X, Threads, LinkedIn – only for enabled platforms)
    3. Review drafts (human approval step)
    4. Publish only APPROVED posts
    """
    init_db()
    cfg = get_config()

    # Basic info
    modes_cfg = cfg.get("modes", {})
    dry_run = bool(modes_cfg.get("dry_run", True))

    platforms_cfg = cfg.get("platforms", {})
    x_enabled = bool(platforms_cfg.get("x_enabled", True))
    threads_enabled = bool(platforms_cfg.get("threads_enabled", True))
    linkedin_enabled = bool(platforms_cfg.get("linkedin_enabled", True))

    print("\n=== CONFIG SUMMARY ===")
    print(f"dry_run         = {dry_run}")
    print(f"x_enabled       = {x_enabled}")
    print(f"threads_enabled = {threads_enabled}")
    print(f"linkedin_enabled= {linkedin_enabled}")

    # Input file paths
    input_cfg = cfg.get("input_files", {})
    diary_path = input_cfg.get("diary_path", "data/diary.txt")
    x_threads_path = input_cfg.get("x_threads_path", "data/x_threads.txt")

    print("\n=== INPUT FILES ===")
    print(f"Diary file      = {diary_path}")
    print(f"X/Threads file  = {x_threads_path}")

    processed_diary_ids = []

    # === 3) PROCESS X/THREADS ===
    x_threads_text = read_text_file(x_threads_path)
    res1 = _run_for_source(x_threads_text, source="x_threads_file")
    if res1 and res1.get("ok"):
        processed_diary_ids.append(res1["diary_id"])

    # === 4) PROCESS DIARY ===
    diary_text = read_text_file(diary_path)
    res2 = _run_for_source(diary_text, source="diary_file")
    if res2 and res2.get("ok"):
        processed_diary_ids.append(res2["diary_id"])

    # === 4.5) HUMAN REVIEW ===
    print("\n=== REVIEW DRAFTS ===")
    review_drafts_interactive(allowed_diary_ids=processed_diary_ids)

    # === 5) PUBLISH APPROVED POSTS ===
    print("\n=== PUBLISHING PIPELINE ===")
    run_publishing_pipeline(allowed_diary_ids=processed_diary_ids)

    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
