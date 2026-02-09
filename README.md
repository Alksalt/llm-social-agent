# Telegram LLM Social Agent

Turn diary-style messages into reviewable social drafts in Telegram, then publish to X, Threads, or LinkedIn.

## What You Get

- Send normal text messages as entries
- Trigger draft generation with `#draft` or `/draft`
- Review each draft with buttons (`Approve`, `Approve + Publish`, `Regenerate`, `Edit`, `Schedule`)
- Approval-first publishing flow by default
- Multi-LLM routing with fallback (OpenAI, Anthropic, Gemini)
- SQLite persistence, logs, and scheduler support

## Quick Start

1. Create env file:

```bash
cp .env.example .env
```

2. Fill at minimum:
- `TELEGRAM_BOT_TOKEN`
- One or more LLM keys:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GEMINI_API_KEY` or `GOOGLE_API_KEY`

3. Install:

```bash
uv sync --extra dev
```

4. Init DB and run:

```bash
python main.py init-db
python main.py
```

Default is dry-run mode (`dry_run: true`), so publishes are simulated until you switch it off.

## Daily Usage

### Fast flow from one message

Send:

```text
Today I shipped scheduler improvements and fixed fallback logic. #draft linkedin
```

Bot behavior:
1. Stores entry
2. Generates drafts
3. Shows draft cards with buttons

### Publish flow

- `Approve` -> bot asks: "Publish now?" (Yes/Not now)
- `Approve + Publish` -> auto-approves (if needed) and publishes immediately
- `/publish` -> publishes all approved drafts
- `/publish 12` -> publishes one draft by ID

### Scheduling

1. Click `Schedule` on a draft
2. Send time in `Europe/Oslo` format:
   - `YYYY-MM-DD HH:MM`
   - example: `2026-02-10 09:30`
3. Run scheduler worker periodically:

```bash
python main.py run-scheduler
```

## Commands

- `/start`
- `/capture` start multi-message capture
- `/done` store captured buffer as one entry
- `/draft [platforms]`
- `/publish [draft_id]`
- `/queue` show pending drafts
- `/status` show dry-run, last publish, LLM usage
- `/dryrun on|off`
- `/undo`
- `/style show`
- `/provider show`
- `/provider set <stage> <provider:model,provider:model>`

## Message Directives

- `#draft` generate drafts
- `#publish x linkedin threads` generate drafts for listed platforms and guide you through publish flow
- `#private` store only; skip drafting/publishing
- `#strict` more conservative wording

## Model Routing

Configure in `/Users/alt/Library/CloudStorage/OneDrive-Personal/Portfolio/llm-social-agent/config/settings.yaml`:

- `routing.summarize`
- `routing.draft_x`
- `routing.draft_threads`
- `routing.draft_linkedin`
- `routing.check`

Router tries models in order and falls back on provider/model failures.
Draft cards also show which model wrote the draft and which model made the summary.

## STYLE.md and MODELS.md

By default:
- `./STYLE.md`
- `./MODELS.md`

If missing, the bot uses safe built-in defaults.

## Troubleshooting

- "Entry stored, but no drafts":
  - You did not include `#draft` or `#publish`
  - Or all target platforms are disabled in config
- "Published 0/N approved drafts":
  - Inspect per-draft reasons in bot response
  - Most common: missing platform credentials or validation failure
- Anthropic/Gemini errors:
  - confirm env vars loaded correctly
  - verify model names in `routing`

## Tests

```bash
uv run pytest
```
