"""Telegram bot handlers and app wiring."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from .directives import parse_directives, parse_platform_args
from .llm.router import LLMRouter
from .models import (
    append_capture_text,
    clear_user_state,
    end_capture_session,
    get_capture_session,
    get_connection,
    get_draft,
    get_entry,
    get_global_setting,
    list_user_entries,
    get_user_state,
    set_global_setting,
    set_user_state,
    start_capture_session,
)
from .models_loader import load_models_reference
from .orchestrator import (
    edit_draft,
    enabled_platforms,
    format_draft_message,
    generate_drafts,
    ingest_entry,
    list_queue,
    parse_user_datetime,
    publish_approved_queue,
    publish_draft,
    regenerate_draft,
    schedule_draft,
    set_draft_decision,
    status_snapshot,
    undo_last_action,
)
from .publishing import get_clients
from .style_loader import load_style
from .utils import json_loads
from .validators import validate_draft
from .llm.types import ProviderError

try:
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.ext import (
        Application,
        ApplicationBuilder,
        CallbackQueryHandler,
        CommandHandler,
        ContextTypes,
        MessageHandler,
        filters,
    )
except Exception:  # pragma: no cover - import failure tested manually at runtime
    Application = None


class TelegramAgentBot:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.db_path = str(config["database"]["path"])
        self.style_context = load_style(config["paths"]["style_path"])
        self.models_reference = load_models_reference(config["paths"]["models_path"])
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def _draft_keyboard(draft_id: int) -> InlineKeyboardMarkup:
        buttons = [
            [
                InlineKeyboardButton("Approve", callback_data=f"draft:approve:{draft_id}"),
                InlineKeyboardButton("Reject", callback_data=f"draft:reject:{draft_id}"),
            ],
            [
                InlineKeyboardButton("Regenerate", callback_data=f"draft:regenerate:{draft_id}"),
                InlineKeyboardButton("Edit", callback_data=f"draft:edit:{draft_id}"),
            ],
            [
                InlineKeyboardButton("Approve + Publish", callback_data=f"draft:publish:{draft_id}"),
                InlineKeyboardButton("Schedule", callback_data=f"draft:schedule:{draft_id}"),
            ],
        ]
        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def _publish_prompt_keyboard(draft_id: int) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes, Publish", callback_data=f"draft:pubyes:{draft_id}"),
                    InlineKeyboardButton("Not now", callback_data=f"draft:publater:{draft_id}"),
                ]
            ]
        )

    @staticmethod
    def _user_id(update: Update) -> str:
        return str(update.effective_user.id)

    async def _send_draft(self, update: Update, draft: Dict[str, Any], validation: Dict[str, Any] | None = None) -> None:
        msg = format_draft_message(draft, validation)
        await update.effective_chat.send_message(msg, reply_markup=self._draft_keyboard(draft["id"]))

    def _router(self, conn):
        return LLMRouter(self.config, conn, models_reference=self.models_reference)

    @staticmethod
    def _publish_hint_for_failure(result: Dict[str, Any]) -> str:
        reason = result.get("reason") or "unknown_error"
        if reason == "approval_required":
            return "Needs approval first. Tap Approve or use /queue."
        if reason == "invalid_draft":
            return "Draft failed validation (likely over char limit). Regenerate or edit."
        if reason == "publish_failed":
            err = result.get("error", "")
            if "Missing LinkedIn credentials" in err:
                return "Missing LinkedIn credentials. Check LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN."
            if "Missing X API credentials" in err:
                return "Missing X credentials. Check X_* env vars."
            if "Missing Threads credentials" in err:
                return "Missing Threads credentials. Check THREADS_* env vars."
            return f"Publisher error: {err[:180]}"
        if reason == "missing_platform_client":
            return "No platform client configured."
        return reason

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.message.reply_text(
            "Hi. I can turn your diary text into social drafts and publish after approval.\n\n"
            "Main flow:\n"
            "1) Send text (+ optional #draft or #publish linkedin)\n"
            "2) Review draft cards\n"
            "3) Approve/Publish or Schedule\n\n"
            "Commands: /capture /done /draft [platforms] /publish [draft_id] /queue /status /dryrun on|off /undo\n"
            "Directives: #draft #publish x linkedin threads #private #strict"
        )

    async def capture(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = self._user_id(update)
        with get_connection(self.db_path) as conn:
            start_capture_session(conn, user_id)
        await update.message.reply_text("Capture started. Send one or more messages, then /done.")

    async def done(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = self._user_id(update)
        with get_connection(self.db_path) as conn:
            session = end_capture_session(conn, user_id)
        if not session or not session.get("buffer_text", "").strip():
            await update.message.reply_text("No active capture session or empty buffer.")
            return
        await self._process_entry_text(update, session["buffer_text"], user_id)

    async def draft(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = self._user_id(update)
        with get_connection(self.db_path) as conn:
            entry = None
            for candidate in list_user_entries(conn, user_id, limit=20):
                flags = json_loads(candidate.get("flags_json"))
                if not flags.get("private"):
                    entry = candidate
                    break
            if not entry:
                await update.message.reply_text(
                    "No draftable entries found. Send a non-#private message first or use /capture."
                )
                return
            platforms = parse_platform_args(context.args, enabled_platforms(self.config))
            flags = json_loads(entry.get("flags_json"))
            is_strict = bool(flags.get("strict", False))
            router = self._router(conn)
            await update.message.reply_text(
                f"Generating drafts for: {', '.join(platforms)}"
                + (" (strict mode)." if is_strict else ".")
            )
            result = generate_drafts(
                conn,
                self.config,
                router,
                self.style_context,
                entry_id=entry["id"],
                platforms=platforms,
                is_strict=is_strict,
            )

        for row in result["drafts"]:
            await self._send_draft(update, row["draft"], row["validation"])

    async def publish(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = self._user_id(update)
        clients = get_clients()

        with get_connection(self.db_path) as conn:
            if context.args:
                try:
                    draft_id = int(context.args[0])
                except ValueError:
                    await update.message.reply_text("Usage: /publish [draft_id]")
                    return
                result = publish_draft(conn, self.config, draft_id=draft_id, clients=clients)
                if result["ok"]:
                    await update.message.reply_text(f"Draft {draft_id} published (dry_run={result['dry_run']}).")
                else:
                    await update.message.reply_text(
                        f"Publish failed for draft #{draft_id}: {self._publish_hint_for_failure(result)}"
                    )
                return

            queue_result = publish_approved_queue(conn, self.config, user_id=user_id, clients=clients)

        ok_count = sum(1 for item in queue_result["results"] if item.get("ok"))
        total = len(queue_result["results"])
        if total == 0:
            await update.message.reply_text("No approved drafts found. Use /queue to approve drafts first.")
            return

        lines = [f"Published {ok_count}/{total} approved drafts."]
        for item in queue_result["results"]:
            draft_id = item.get("draft_id", "?")
            platform = str(item.get("platform", "?")).upper()
            if item.get("ok"):
                lines.append(f"- Draft #{draft_id} ({platform}): published (dry_run={item.get('dry_run')})")
            else:
                lines.append(f"- Draft #{draft_id} ({platform}): {self._publish_hint_for_failure(item)}")
        await update.message.reply_text("\n".join(lines))

    async def queue(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = self._user_id(update)
        with get_connection(self.db_path) as conn:
            rows = list_queue(conn, user_id)
        if not rows:
            await update.message.reply_text("No pending drafts.")
            return

        await update.message.reply_text(f"Pending drafts: {len(rows)}")
        for draft in rows[:10]:
            validation = validate_draft(draft["platform"], draft["content"], self.config)
            await self._send_draft(update, draft, validation)

    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        with get_connection(self.db_path) as conn:
            snap = status_snapshot(conn, self.config)
        last_publish = snap["last_publish"]
        last = last_publish["attempted_at"] if last_publish else "none"
        costs = snap["costs"]
        await update.message.reply_text(
            "\n".join(
                [
                    f"dry_run={snap['dry_run']}",
                    f"last_publish={last}",
                    f"llm_calls={costs['calls']}",
                    f"tokens_in={costs['tokens_in']} tokens_out={costs['tokens_out']}",
                    f"cost_usd={costs['cost_usd']:.6f}",
                ]
            )
        )

    async def dryrun(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args or context.args[0].lower() not in {"on", "off"}:
            await update.message.reply_text("Usage: /dryrun on|off")
            return

        value = context.args[0].lower() == "on"
        with get_connection(self.db_path) as conn:
            set_global_setting(conn, "dry_run", value)
        await update.message.reply_text(f"dry_run set to {value}")

    async def undo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = self._user_id(update)
        with get_connection(self.db_path) as conn:
            result = undo_last_action(conn, user_id)
        if result["ok"]:
            await update.message.reply_text(f"Undo complete ({result['action_type']}).")
        else:
            await update.message.reply_text(f"Undo failed: {result['reason']}")

    async def style(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if context.args and context.args[0].lower() == "show":
            contract = self.style_context["contract"]
            await update.message.reply_text(f"STYLE source: {'loaded' if self.style_context['exists'] else 'fallback'}")
            await update.message.reply_text(contract[:3000])
            return
        await update.message.reply_text("Usage: /style show")

    async def provider(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Usage: /provider show | /provider set <stage> <provider:model,provider:model>")
            return

        action = context.args[0].lower()
        if action == "show":
            routes = self.config.get("routing", {})
            lines = [f"{stage}: {', '.join(values)}" for stage, values in routes.items()]
            models_state = "loaded" if self.models_reference.get("exists") else "fallback"
            await update.message.reply_text(f"MODELS source: {models_state}\n" + "\n".join(lines))
            return

        if action == "set" and len(context.args) >= 3:
            stage = context.args[1]
            route_csv = " ".join(context.args[2:])
            routes = [item.strip() for item in route_csv.split(",") if item.strip()]
            if not routes:
                await update.message.reply_text("No routes provided.")
                return
            self.config.setdefault("routing", {})[stage] = routes
            await update.message.reply_text(f"Updated route for {stage}: {', '.join(routes)}")
            return

        await update.message.reply_text("Usage: /provider show | /provider set <stage> <provider:model,provider:model>")

    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = self._user_id(update)

        try:
            _, action, raw_id = query.data.split(":", 2)
            draft_id = int(raw_id)
        except Exception:
            await query.edit_message_text("Invalid action payload.")
            return

        with get_connection(self.db_path) as conn:
            if action == "approve":
                result = set_draft_decision(conn, user_id, draft_id, "approved")
                if result["ok"]:
                    await query.edit_message_text(f"Draft {draft_id} approved.")
                    await update.effective_chat.send_message(
                        f"Draft {draft_id} approved. Publish now?",
                        reply_markup=self._publish_prompt_keyboard(draft_id),
                    )
                else:
                    await query.edit_message_text(f"Failed: {result['reason']}")
                return

            if action == "reject":
                result = set_draft_decision(conn, user_id, draft_id, "rejected")
                if result["ok"]:
                    await query.edit_message_text(f"Draft {draft_id} rejected.")
                else:
                    await query.edit_message_text(f"Failed: {result['reason']}")
                return

            if action == "regenerate":
                router = self._router(conn)
                result = regenerate_draft(conn, self.config, router, self.style_context, user_id, draft_id)
                if result["ok"]:
                    draft = result["draft"]
                    validation = result["validation"]
                    await query.edit_message_text("Regenerated. New version below.")
                    await update.effective_chat.send_message(
                        format_draft_message(draft, validation),
                        reply_markup=self._draft_keyboard(draft["id"]),
                    )
                else:
                    await query.edit_message_text(f"Failed: {result['reason']}")
                return

            if action == "edit":
                set_user_state(conn, user_id, "awaiting_edit", {"draft_id": draft_id})
                await query.edit_message_text(
                    f"Send replacement text for draft {draft_id}. It will be saved as a new version."
                )
                return

            if action == "publish":
                draft = get_draft(conn, draft_id)
                if draft and draft.get("status") != "approved":
                    set_draft_decision(conn, user_id, draft_id, "approved")
                result = publish_draft(conn, self.config, draft_id, clients=get_clients())
                if result["ok"]:
                    await query.edit_message_text(f"Draft {draft_id} published (dry_run={result['dry_run']}).")
                else:
                    await query.edit_message_text(
                        f"Publish failed for draft #{draft_id}: {self._publish_hint_for_failure(result)}"
                    )
                return

            if action == "pubyes":
                result = publish_draft(conn, self.config, draft_id, clients=get_clients())
                if result["ok"]:
                    await query.edit_message_text(f"Draft {draft_id} published (dry_run={result['dry_run']}).")
                else:
                    await query.edit_message_text(
                        f"Publish failed for draft #{draft_id}: {self._publish_hint_for_failure(result)}"
                    )
                return

            if action == "publater":
                await query.edit_message_text(f"Kept draft {draft_id} approved. Use /publish when ready.")
                return

            if action == "schedule":
                set_user_state(conn, user_id, "awaiting_schedule", {"draft_id": draft_id})
                await query.edit_message_text(
                    f"Send schedule time for draft {draft_id} in Europe/Oslo: YYYY-MM-DD HH:MM"
                )
                return

        await query.edit_message_text("Unknown action.")

    async def message_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        user_id = self._user_id(update)
        text = update.message.text.strip()

        with get_connection(self.db_path) as conn:
            state = get_user_state(conn, user_id)
            if state:
                state_name = state["state"]
                data = json_loads(state["data_json"])
                if state_name == "awaiting_edit":
                    draft_id = int(data.get("draft_id", 0))
                    result = edit_draft(conn, self.config, user_id, draft_id, text)
                    clear_user_state(conn, user_id)
                    if result["ok"]:
                        draft = result["draft"]
                        await update.message.reply_text("Edited. New draft version:")
                        await update.message.reply_text(
                            format_draft_message(draft, result["validation"]),
                            reply_markup=self._draft_keyboard(draft["id"]),
                        )
                    else:
                        await update.message.reply_text(f"Edit failed: {result['reason']}")
                    return

                if state_name == "awaiting_schedule":
                    draft_id = int(data.get("draft_id", 0))
                    try:
                        dt = parse_user_datetime(text, self.config.get("timezone", "Europe/Oslo"))
                    except ValueError as exc:
                        await update.message.reply_text(str(exc))
                        return
                    result = schedule_draft(conn, user_id, draft_id, dt.astimezone(timezone.utc).isoformat())
                    clear_user_state(conn, user_id)
                    if result["ok"]:
                        await update.message.reply_text(f"Draft {draft_id} scheduled for {dt.isoformat()}")
                    else:
                        await update.message.reply_text(f"Schedule failed: {result['reason']}")
                    return

            session = get_capture_session(conn, user_id)
            if session:
                updated = append_capture_text(conn, user_id, text)
                total_len = len(updated["buffer_text"]) if updated else 0
                await update.message.reply_text(f"Captured. Current buffer length: {total_len} chars. /done when ready.")
                return

        await self._process_entry_text(update, text, user_id)

    async def _process_entry_text(self, update: Update, text: str, user_id: str) -> None:
        directives = parse_directives(text)
        cleaned_text = directives["cleaned_text"]
        flags = directives["flags"]

        with get_connection(self.db_path) as conn:
            ingest = ingest_entry(conn, user_id, cleaned_text, flags=flags, source="telegram")
            if not ingest["ok"]:
                reason = ingest["reason"]
                if reason == "duplicate":
                    await update.effective_chat.send_message("Duplicate entry detected. Skipped storage.")
                else:
                    await update.effective_chat.send_message(f"Entry skipped: {reason}")
                return

            entry = ingest["entry"]
            await update.effective_chat.send_message(f"Entry stored: #{entry['id']}")

            if flags.get("private"):
                await update.effective_chat.send_message("Marked #private. No drafting or publishing will run.")
                return

            wants_draft = bool(flags.get("draft")) or bool(flags.get("publish"))
            if not wants_draft:
                await update.effective_chat.send_message(
                    "Saved. Next step: send /draft linkedin (or include #draft in your message)."
                )
                return

            requested = flags.get("publish_platforms") or []
            platforms = requested or enabled_platforms(self.config)
            await update.effective_chat.send_message(
                f"Generating drafts for: {', '.join(platforms)}. This can take a few seconds..."
            )
            if flags.get("publish"):
                await update.effective_chat.send_message(
                    "You used #publish. Approval is still required by default, so review and tap Approve + Publish."
                )
            router = self._router(conn)
            try:
                draft_result = generate_drafts(
                    conn,
                    self.config,
                    router,
                    self.style_context,
                    entry_id=entry["id"],
                    platforms=platforms,
                    is_strict=bool(flags.get("strict")),
                )
            except ProviderError:
                await update.effective_chat.send_message(
                    "Draft generation failed across all providers. Check API keys/model names or set llm_enabled=false."
                )
                return

        if not draft_result["drafts"]:
            await update.effective_chat.send_message(
                "No drafts were generated. Check platform toggles in settings.yaml and try /draft linkedin."
            )
            return

        await update.effective_chat.send_message(
            f"Draft generation complete: {len(draft_result['drafts'])} draft(s). Review below."
        )
        for row in draft_result["drafts"]:
            await self._send_draft(update, row["draft"], row["validation"])

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.logger.exception("Unhandled bot error", exc_info=context.error)
        if isinstance(update, Update) and update.effective_chat:
            await update.effective_chat.send_message(
                "Unexpected error while processing your request. Try /status, then retry."
            )

    def build_application(self) -> Application:
        if ApplicationBuilder is None:
            raise RuntimeError("python-telegram-bot is not installed")

        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")

        app = ApplicationBuilder().token(token).build()
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("capture", self.capture))
        app.add_handler(CommandHandler("done", self.done))
        app.add_handler(CommandHandler("draft", self.draft))
        app.add_handler(CommandHandler("publish", self.publish))
        app.add_handler(CommandHandler("queue", self.queue))
        app.add_handler(CommandHandler("status", self.status))
        app.add_handler(CommandHandler("dryrun", self.dryrun))
        app.add_handler(CommandHandler("undo", self.undo))
        app.add_handler(CommandHandler("style", self.style))
        app.add_handler(CommandHandler("provider", self.provider))
        app.add_handler(CallbackQueryHandler(self.callback_handler, pattern=r"^draft:"))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.message_handler))
        app.add_error_handler(self.error_handler)
        return app

    def run_polling(self) -> None:
        app = self.build_application()
        app.run_polling(poll_interval=float(self.config["telegram"].get("poll_interval_seconds", 1)))
