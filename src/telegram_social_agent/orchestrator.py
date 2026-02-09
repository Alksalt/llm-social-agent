"""Pure orchestration functions for entry -> draft -> approval -> publish."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List

from .models import (
    clear_user_state,
    create_draft,
    create_entry,
    create_publish_log,
    create_undo_action,
    delete_draft,
    delete_entry,
    get_cost_summary,
    get_draft,
    get_entry,
    get_global_setting,
    get_last_publish_attempt,
    get_last_undo_action,
    get_latest_entry_for_user,
    list_approved_drafts,
    list_due_scheduled_drafts,
    list_pending_drafts,
    mark_undo_action_done,
    update_draft_status,
)
from .prompts import build_draft_prompt, build_summary_prompt, build_system_prompt
from .utils import hash_text, json_loads
from .validators import get_limit, truncate_to_limit, validate_draft
from .llm.types import ProviderError

PLATFORMS = ("x", "threads", "linkedin")


def enabled_platforms(config: Dict[str, Any]) -> List[str]:
    p = config.get("platforms", {})
    return [
        platform
        for platform, key in (
            ("x", "x_enabled"),
            ("threads", "threads_enabled"),
            ("linkedin", "linkedin_enabled"),
        )
        if bool(p.get(key, True))
    ]


def _llm_enabled(config: Dict[str, Any]) -> bool:
    return bool(config.get("modes", {}).get("llm_enabled", True))


def effective_dry_run(conn, config: Dict[str, Any]) -> bool:
    default = bool(config.get("modes", {}).get("dry_run", True))
    override = get_global_setting(conn, "dry_run", default)
    return bool(override)


def ingest_entry(
    conn,
    user_id: str,
    entry_text: str,
    flags: Dict[str, Any] | None = None,
    source: str = "telegram",
) -> Dict[str, Any]:
    cleaned = (entry_text or "").strip()
    if not cleaned:
        return {"ok": False, "reason": "empty", "entry": None}

    text_hash = hash_text(cleaned)
    from .models import get_entry_by_hash

    existing = get_entry_by_hash(conn, user_id=user_id, text_hash=text_hash)
    if existing:
        return {"ok": False, "reason": "duplicate", "entry": existing}

    entry = create_entry(
        conn,
        user_id=user_id,
        text=cleaned,
        text_hash=text_hash,
        source=source,
        flags=flags or {},
    )
    create_undo_action(conn, user_id, "entry_create", {"entry_id": entry["id"]})
    return {"ok": True, "reason": None, "entry": entry}


def summarize_entry(
    conn,
    config: Dict[str, Any],
    router,
    style_context: Dict[str, Any],
    entry_id: int,
) -> tuple[str, Dict[str, Any]]:
    entry = get_entry(conn, entry_id)
    if not entry:
        raise ValueError(f"Entry not found: {entry_id}")

    text = entry["text"]
    if not _llm_enabled(config) or router is None:
        return text[:300], {
            "mode": "fallback",
            "stage": "summarize",
            "reason": "llm_disabled_or_router_missing",
        }

    system = build_system_prompt(style_context["contract"])
    prompt = build_summary_prompt(text)
    try:
        result = router.generate(
            stage="summarize",
            prompt=prompt,
            system=system,
            meta={"entry_id": entry_id},
        )
        return (
            result.text or text[:300],
            {
                "mode": "llm",
                "stage": "summarize",
                "provider": result.provider,
                "model": result.model,
            },
        )
    except ProviderError as exc:
        return text[:300], {
            "mode": "fallback",
            "stage": "summarize",
            "reason": str(exc)[:240],
        }


def _deterministic_draft(platform: str, summary: str, entry_text: str, limit: int) -> str:
    base = f"[{platform.upper()}] {summary}" if summary else f"[{platform.upper()}] {entry_text}"
    return truncate_to_limit(base, limit)


def _stage_for_platform(platform: str) -> str:
    return f"draft_{platform}"


def generate_drafts(
    conn,
    config: Dict[str, Any],
    router,
    style_context: Dict[str, Any],
    entry_id: int,
    platforms: List[str] | None = None,
    is_strict: bool = False,
) -> Dict[str, Any]:
    entry = get_entry(conn, entry_id)
    if not entry:
        return {"ok": False, "reason": "entry_not_found", "drafts": []}

    user_id = entry["user_id"]
    platform_list = platforms or enabled_platforms(config)
    summary, summary_meta = summarize_entry(conn, config, router, style_context, entry_id)
    drafts: List[Dict[str, Any]] = []
    system = build_system_prompt(style_context["contract"])

    for platform in platform_list:
        if platform not in PLATFORMS:
            continue
        limit = get_limit(config, platform)

        if _llm_enabled(config) and router is not None:
            prompt = build_draft_prompt(
                platform=platform,
                entry_text=entry["text"],
                summary=summary,
                style_template=style_context["templates"][platform],
                is_strict=is_strict,
                limit=limit,
            )
            try:
                result = router.generate(
                    stage=_stage_for_platform(platform),
                    prompt=prompt,
                    system=system,
                    meta={"entry_id": entry_id, "platform": platform, "strict": is_strict},
                )
                content = result.text.strip()
                generation_meta = {
                    "mode": "llm",
                    "stage": _stage_for_platform(platform),
                    "provider": result.provider,
                    "model": result.model,
                }
            except ProviderError:
                content = _deterministic_draft(platform, summary, entry["text"], limit)
                generation_meta = {
                    "mode": "fallback",
                    "stage": _stage_for_platform(platform),
                    "reason": "provider_error",
                }
        else:
            content = _deterministic_draft(platform, summary, entry["text"], limit)
            generation_meta = {
                "mode": "fallback",
                "stage": _stage_for_platform(platform),
                "reason": "llm_disabled_or_router_missing",
            }

        validation = validate_draft(platform, content, config)
        if not validation["ok"]:
            if _llm_enabled(config) and router is not None:
                retry_prompt = (
                    f"Rewrite this {platform} draft under {limit} chars without losing the core meaning.\n\n"
                    f"Original draft:\n{content}"
                )
                try:
                    retry_result = router.generate(
                        stage=_stage_for_platform(platform),
                        prompt=retry_prompt,
                        system=system,
                        meta={"entry_id": entry_id, "platform": platform, "retry": True},
                    )
                    content = retry_result.text.strip()
                    validation = validate_draft(platform, content, config)
                except ProviderError:
                    content = truncate_to_limit(content, limit)
                    validation = validate_draft(platform, content, config)
            if not validation["ok"]:
                content = truncate_to_limit(content, limit)
                validation = validate_draft(platform, content, config)

        draft = create_draft(
            conn,
            entry_id=entry_id,
            platform=platform,
            content=content,
            status="pending",
            meta={
                "summary": summary,
                "summary_meta": summary_meta,
                "generation": generation_meta,
                "strict": is_strict,
                "validation": validation,
            },
        )
        create_undo_action(conn, user_id, "draft_create", {"draft_id": draft["id"]})
        drafts.append({"draft": draft, "validation": validation})

    return {"ok": True, "reason": None, "summary": summary, "drafts": drafts}


def set_draft_decision(conn, user_id: str, draft_id: int, new_status: str) -> Dict[str, Any]:
    draft = get_draft(conn, draft_id)
    if not draft:
        return {"ok": False, "reason": "draft_not_found", "draft_id": draft_id}

    previous = {"status": draft["status"], "scheduled_at": draft["scheduled_at"]}
    updated = update_draft_status(conn, draft_id, new_status, draft["scheduled_at"])
    create_undo_action(
        conn,
        user_id,
        "draft_status_update",
        {
            "draft_id": draft_id,
            "previous_status": previous["status"],
            "previous_scheduled_at": previous["scheduled_at"],
        },
    )
    return {"ok": True, "draft": updated}


def regenerate_draft(
    conn,
    config: Dict[str, Any],
    router,
    style_context: Dict[str, Any],
    user_id: str,
    draft_id: int,
) -> Dict[str, Any]:
    draft = get_draft(conn, draft_id)
    if not draft:
        return {"ok": False, "reason": "draft_not_found"}

    entry = get_entry(conn, draft["entry_id"])
    if not entry:
        return {"ok": False, "reason": "entry_not_found"}

    draft_meta = json_loads(draft.get("meta_json"))
    summary = str(draft_meta.get("summary") or "")
    is_strict = bool(draft_meta.get("strict", False))
    platform = draft["platform"]
    limit = get_limit(config, platform)

    if _llm_enabled(config) and router is not None:
        prompt = (
            f"Regenerate this {platform} draft as a fresh alternative. Keep under {limit} chars.\n\n"
            f"Diary:\n{entry['text']}\n\nSummary:\n{summary}\n\nPrevious draft:\n{draft['content']}"
        )
        try:
            result = router.generate(
                stage=_stage_for_platform(platform),
                prompt=prompt,
                system=build_system_prompt(style_context["contract"]),
                meta={"entry_id": entry["id"], "platform": platform, "regenerate_of": draft_id},
            )
            content = result.text.strip()
        except ProviderError:
            content = _deterministic_draft(platform, summary, entry["text"], limit)
    else:
        content = _deterministic_draft(platform, summary, entry["text"], limit)

    validation = validate_draft(platform, content, config)
    if not validation["ok"]:
        content = truncate_to_limit(content, limit)
        validation = validate_draft(platform, content, config)

    update_draft_status(conn, draft_id, "rejected", draft.get("scheduled_at"))
    new_draft = create_draft(
        conn,
        entry_id=entry["id"],
        platform=platform,
        content=content,
        status="pending",
        meta={
            "summary": summary,
            "strict": is_strict,
            "regenerated_from": draft_id,
            "validation": validation,
        },
    )
    create_undo_action(conn, user_id, "draft_create", {"draft_id": new_draft["id"]})
    return {"ok": True, "draft": new_draft, "validation": validation}


def edit_draft(
    conn,
    config: Dict[str, Any],
    user_id: str,
    draft_id: int,
    replacement_text: str,
) -> Dict[str, Any]:
    old = get_draft(conn, draft_id)
    if not old:
        return {"ok": False, "reason": "draft_not_found"}

    platform = old["platform"]
    limit = get_limit(config, platform)
    content = truncate_to_limit(replacement_text.strip(), limit)
    validation = validate_draft(platform, content, config)

    update_draft_status(conn, draft_id, "rejected", old.get("scheduled_at"))
    new_draft = create_draft(
        conn,
        entry_id=old["entry_id"],
        platform=platform,
        content=content,
        status="pending",
        meta={"edited_from": draft_id, "validation": validation},
    )
    create_undo_action(conn, user_id, "draft_create", {"draft_id": new_draft["id"]})
    return {"ok": True, "draft": new_draft, "validation": validation}


def schedule_draft(conn, user_id: str, draft_id: int, scheduled_at_iso: str) -> Dict[str, Any]:
    draft = get_draft(conn, draft_id)
    if not draft:
        return {"ok": False, "reason": "draft_not_found"}

    previous = {"status": draft["status"], "scheduled_at": draft["scheduled_at"]}
    updated = update_draft_status(conn, draft_id, "scheduled", scheduled_at_iso)
    create_undo_action(
        conn,
        user_id,
        "draft_status_update",
        {
            "draft_id": draft_id,
            "previous_status": previous["status"],
            "previous_scheduled_at": previous["scheduled_at"],
        },
    )
    return {"ok": True, "draft": updated}


def publish_draft(conn, config: Dict[str, Any], draft_id: int, clients: Dict[str, Any], force: bool = False) -> Dict[str, Any]:
    draft = get_draft(conn, draft_id)
    if not draft:
        return {"ok": False, "reason": "draft_not_found"}

    approval_required = bool(config.get("modes", {}).get("approval_required", True))
    if approval_required and not force and draft["status"] not in {"approved", "scheduled"}:
        return {"ok": False, "reason": "approval_required", "draft_id": draft["id"], "platform": draft["platform"]}

    validation = validate_draft(draft["platform"], draft["content"], config)
    if not validation["ok"]:
        return {
            "ok": False,
            "reason": "invalid_draft",
            "validation": validation,
            "draft_id": draft["id"],
            "platform": draft["platform"],
        }

    dry_run = effective_dry_run(conn, config)
    client = clients.get(draft["platform"])
    if client is None:
        return {"ok": False, "reason": "missing_platform_client", "draft_id": draft["id"], "platform": draft["platform"]}

    try:
        response = client.publish(draft["content"], dry_run=dry_run)
        create_publish_log(
            conn,
            draft_id=draft["id"],
            platform=draft["platform"],
            success=True,
            response=response,
            error=None,
        )
        update_draft_status(conn, draft["id"], "published", None)
        return {
            "ok": True,
            "draft_id": draft["id"],
            "platform": draft["platform"],
            "response": response,
            "dry_run": dry_run,
        }
    except Exception as exc:
        create_publish_log(
            conn,
            draft_id=draft["id"],
            platform=draft["platform"],
            success=False,
            response=None,
            error=str(exc),
        )
        return {
            "ok": False,
            "reason": "publish_failed",
            "error": str(exc),
            "dry_run": dry_run,
            "draft_id": draft["id"],
            "platform": draft["platform"],
        }


def publish_approved_queue(conn, config: Dict[str, Any], user_id: str, clients: Dict[str, Any]) -> Dict[str, Any]:
    drafts = list_approved_drafts(conn, user_id=user_id)
    results = []
    for draft in drafts:
        results.append(publish_draft(conn, config, draft["id"], clients=clients))
    return {"ok": True, "results": results}


def run_scheduler_once(conn, config: Dict[str, Any], now_iso: str, clients: Dict[str, Any]) -> Dict[str, Any]:
    due = list_due_scheduled_drafts(conn, now_iso=now_iso)
    results = []
    for draft in due:
        results.append(publish_draft(conn, config, draft["id"], clients=clients, force=True))
    return {"ok": True, "count": len(results), "results": results}


def list_queue(conn, user_id: str) -> List[Dict[str, Any]]:
    return list_pending_drafts(conn, user_id=user_id)


def status_snapshot(conn, config: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dry_run": effective_dry_run(conn, config),
        "costs": get_cost_summary(conn),
        "last_publish": get_last_publish_attempt(conn),
    }


def undo_last_action(conn, user_id: str) -> Dict[str, Any]:
    action = get_last_undo_action(conn, user_id)
    if not action:
        return {"ok": False, "reason": "nothing_to_undo"}

    payload = json_loads(action.get("payload_json"))
    action_type = action["action_type"]

    if action_type == "entry_create":
        entry_id = int(payload.get("entry_id", 0))
        if entry_id:
            delete_entry(conn, entry_id)
    elif action_type == "draft_create":
        draft_id = int(payload.get("draft_id", 0))
        if draft_id:
            delete_draft(conn, draft_id)
    elif action_type == "draft_status_update":
        draft_id = int(payload.get("draft_id", 0))
        previous_status = payload.get("previous_status")
        previous_scheduled_at = payload.get("previous_scheduled_at")
        if draft_id and previous_status:
            update_draft_status(conn, draft_id, previous_status, previous_scheduled_at)
    else:
        return {"ok": False, "reason": f"unsupported_undo_action:{action_type}"}

    mark_undo_action_done(conn, action["id"])
    return {"ok": True, "action_type": action_type}


def format_draft_message(draft: Dict[str, Any], validation: Dict[str, Any] | None = None) -> str:
    v = validation
    if not v:
        v = {"ok": True, "length": len(draft["content"]), "limit": "?"}
    meta = json_loads(draft.get("meta_json"))
    generation = meta.get("generation", {}) if isinstance(meta, dict) else {}
    summary_meta = meta.get("summary_meta", {}) if isinstance(meta, dict) else {}

    if generation.get("mode") == "llm":
        writer_line = f"Writer: {generation.get('provider')}:{generation.get('model')}"
    else:
        writer_line = "Writer: template fallback"

    if summary_meta.get("mode") == "llm":
        summary_line = f"Summary model: {summary_meta.get('provider')}:{summary_meta.get('model')}"
    else:
        summary_line = "Summary model: fallback"

    return (
        f"Draft #{draft['id']} | {draft['platform'].upper()} | v{draft['version']} | status={draft['status']}\n"
        f"Validation: {'OK' if v['ok'] else 'TOO LONG'} ({v['length']}/{v['limit']})\n\n"
        f"{writer_line}\n"
        f"{summary_line}\n\n"
        f"{draft['content']}"
    )


def parse_user_datetime(text: str, timezone_name: str) -> datetime:
    from zoneinfo import ZoneInfo

    local_tz = ZoneInfo(timezone_name)
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"):
        try:
            local_dt = datetime.strptime(text.strip(), fmt).replace(tzinfo=local_tz)
            return local_dt
        except ValueError:
            continue
    raise ValueError("Expected datetime format: YYYY-MM-DD HH:MM")
