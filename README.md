# Agentic Social Diary

Turn a daily diary note into platform-ready drafts for X, Threads, and LinkedIn. Drafts are reviewed by you before publishing, and you can run in fully dry-run mode for demos.

## What it does
- Ingests diary text from files (diary + optional x_threads file).
- Generates summaries and platform-specific drafts via LLM (toggleable).
- Validates character limits and stores drafts in SQLite.
- CLI review step to approve drafts.
- Publishes (or simulates) to X, Threads, and LinkedIn.
- Logs publish attempts and LLM token costs.

## Repository layout
- `src/main.py` — CLI entrypoint wiring the whole pipeline.
- `src/core/` — config loader, orchestrator, review loop, publisher, LLM client.
- `src/tools/` — data helpers, validation, content generation, file I/O.
- `src/platform_clients/` — X, Threads, LinkedIn adapters (dry-run friendly).
- `src/db/` — SQLite helpers and schema bootstrap.
- `config/settings.yaml` — toggles, limits, API base URLs, DB path, input files.
- `summary.txt` — detailed flow notes.
- `tests/` — hash helper test and platform client tests.

## Prerequisites
- Python 3.10+
- (Optional) Access keys for X / Threads / LinkedIn if you want real publishes.
- OpenAI API key for LLM generation.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` at repo root for secrets:
```
OPENAI_API_KEY=...
X_API_KEY=...
X_API_KEY_SECRET=...
X_ACCESS_TOKEN=...
X_ACCESS_TOKEN_SECRET=...
THREADS_USER_ID=...
THREADS_ACCESS_TOKEN=...
LINKEDIN_ACCESS_TOKEN=...
LINKEDIN_PERSON_URN=urn:li:person:...
```

## Configuration
Edit `config/settings.yaml`:
- `modes.dry_run` (default true): simulate publishing.
- `modes.llm_enabled` (default true): when false, skip LLM and reuse raw text.
- `platforms.*_enabled`: choose which platforms to target.
- `platform_limits.*_max_chars`: character ceilings for validation/regeneration.
- `posting_limits.linkedin_per_week`: weekly cap enforcement.
- `database.url`: SQLite file (default `data/agent_posts.db`).
- `input_files.diary_path` and `input_files.x_threads_path`: source text files.

## Usage
1) Add your diary text to `data/diary.txt` (and optionally `data/x_threads.txt`).
2) Run the pipeline:
```bash
python -m src.main
```
3) Review drafts in the interactive prompt; approve those you like.
4) Publishing step runs next (dry-run aware). Approved posts are marked published on success.

## Testing
Pytest is configured; install dev deps from `requirements.txt` and run:
```bash
pytest
```

## Notes
- LLM calls and pricing use the OpenAI Responses API; token usage is logged to SQLite.
- If you keep `modes.llm_enabled=false`, the system still deduplicates, validates, and routes posts but skips generation/regeneration. 
- `summary.txt` gives a verbose walkthrough of the pipeline for quick review.
