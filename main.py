"""Entrypoint: run Telegram bot or scheduler jobs."""

from __future__ import annotations

import argparse

from pathlib import Path
import sys

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from telegram_social_agent.config import load_settings
from telegram_social_agent.models import apply_migrations, get_connection
from telegram_social_agent.scheduler import run_due_scheduler
from telegram_social_agent.telegram_bot import TelegramAgentBot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram-driven llm-social-agent")
    parser.add_argument("--settings", default="config/settings.yaml", help="Path to settings.yaml")

    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("run-bot", help="Run Telegram bot (default)")
    subparsers.add_parser("run-scheduler", help="Publish due scheduled drafts")
    subparsers.add_parser("init-db", help="Apply SQLite migrations only")
    return parser


def main() -> None:
    load_dotenv()
    parser = _build_parser()
    args = parser.parse_args()
    command = args.command or "run-bot"

    config = load_settings(args.settings)
    db_path = config["database"]["path"]
    apply_migrations(db_path)

    if command == "init-db":
        print(f"Database initialized at {db_path}")
        return

    if command == "run-scheduler":
        with get_connection(db_path) as conn:
            result = run_due_scheduler(conn, config)
        print(f"Scheduler processed {result['count']} draft(s)")
        for item in result["results"]:
            status = "ok" if item.get("ok") else f"failed:{item.get('reason') or item.get('error')}"
            print(f"- draft_id={item.get('draft_id')} status={status}")
        return

    bot = TelegramAgentBot(config)
    bot.run_polling()


if __name__ == "__main__":
    main()
