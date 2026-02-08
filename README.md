# Telegram LLM Social Agent

A Telegram-bot-driven version of `llm-social-agent`.

Users send diary entries to a Telegram bot, trigger drafting/publishing with commands or hashtags, review drafts with inline buttons, and publish (or dry-run) to X, Threads, and LinkedIn.

## Features

- Telegram-first UX (`/capture`, `/draft`, `/publish`, `/queue`, `/status`, `/undo`, inline draft actions)
- SQLite persistence with migrations
- Per-user dedupe via `UNIQUE(user_id, text_hash)`
- Stage-based pipeline:
  - ingest -> summarize -> generate -> validate -> approve -> publish/schedule
- Dry-run publishing adapters for X, Threads, LinkedIn
- Multi-provider LLM routing by stage with fallback:
  - OpenAI (default)
  - Anthropic
  - Gemini
- Token/cost/latency logging for LLM calls
- STYLE.md and MODELS.md runtime integration with safe fallback

## Repo layout

- `main.py` - bot + scheduler CLI entrypoint
- `config/settings.yaml` - runtime config
- `src/telegram_social_agent/orchestrator.py` - pure pipeline functions
- `src/telegram_social_agent/telegram_bot.py` - Telegram handlers and inline UI
- `src/telegram_social_agent/models.py` - SQLite schema, migrations, and DB helpers
- `src/telegram_social_agent/llm/` - provider routing + provider adapters
- `src/telegram_social_agent/platform_clients/` - social publish adapters
- `tests/` - required pytest coverage

## Setup

1. Create env file from template:

```bash
cp .env.example .env
```

2. Fill tokens/secrets in `.env`.

3. Install dependencies (uv-friendly):

```bash
uv sync
```

or with pip:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Telegram BotFather setup

1. Open Telegram and chat with [@BotFather](https://t.me/BotFather).
2. Run `/newbot` and complete the prompts.
3. Copy the bot token and set `TELEGRAM_BOT_TOKEN` in `.env`.
4. Start your bot and message it directly.

## Run locally (dry-run)

Apply DB migrations:

```bash
python main.py init-db
```

Run bot:

```bash
python main.py
```

`dry_run` defaults to `true`, so publish calls are simulated unless toggled.

## Scheduler job usage

Schedule button stores `scheduled_at` and `status=scheduled`.
Run due jobs with cron/systemd:

```bash
python main.py run-scheduler
```

Default timezone is `Europe/Oslo` (configurable in `settings.yaml`).

## STYLE.md and MODELS.md

The app expects these paths by default:

- `./STYLE.md`
- `./MODELS.md`

Configured via:

- `paths.style_path`
- `paths.models_path`

Behavior:

- If present: loaded at runtime
- If missing: built-in default style contract/templates and default stage routing are used

## Commands and directives

### Commands

- `/start`
- `/capture`
- `/done`
- `/draft [platforms]`
- `/publish [draft_id]`
- `/queue`
- `/status`
- `/dryrun on|off`
- `/undo`
- `/style show`
- `/provider show`
- `/provider set <stage> <provider:model,provider:model>`

### Hashtag directives in messages

- `#draft`
- `#publish x linkedin threads`
- `#private`
- `#strict`

## Routing and provider configuration

Edit `config/settings.yaml`:

- `routing.<stage>` is an ordered list of `provider:model`
- Router tries first provider/model, then falls back on errors/timeouts
- Stage defaults follow policy:
  - summaries = cheaper models
  - draft writing = premium-but-pragmatic models
  - checks = cheapest models

## Tests

```bash
pytest
```

Includes:

- dedupe hashing
- routing fallback
- dry-run platform publish
- validator truncation
- DB migration smoke test
