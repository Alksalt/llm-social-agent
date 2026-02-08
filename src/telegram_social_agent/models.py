"""SQLite schema, migrations, and data access helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .utils import json_dumps, json_loads, utc_now_iso

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            text TEXT NOT NULL,
            text_hash TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'telegram',
            flags_json TEXT NOT NULL DEFAULT '{}',
            UNIQUE(user_id, text_hash)
        );

        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            created_at TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            scheduled_at TEXT,
            meta_json TEXT NOT NULL DEFAULT '{}',
            version INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(entry_id) REFERENCES entries(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS publish_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            draft_id INTEGER NOT NULL,
            platform TEXT NOT NULL,
            attempted_at TEXT NOT NULL,
            success INTEGER NOT NULL,
            response_json TEXT NOT NULL DEFAULT '{}',
            error TEXT,
            FOREIGN KEY(draft_id) REFERENCES drafts(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stage TEXT NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            tokens_in INTEGER NOT NULL DEFAULT 0,
            tokens_out INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            meta_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL UNIQUE,
            started_at TEXT NOT NULL,
            buffer_text TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS settings (
            user_id TEXT PRIMARY KEY,
            preferences_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_entries_user_id ON entries(user_id);
        CREATE INDEX IF NOT EXISTS idx_drafts_entry_id ON drafts(entry_id);
        CREATE INDEX IF NOT EXISTS idx_drafts_status ON drafts(status);
        CREATE INDEX IF NOT EXISTS idx_publish_logs_draft_id ON publish_logs(draft_id);
        CREATE INDEX IF NOT EXISTS idx_llm_calls_stage_created ON llm_calls(stage, created_at);
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS user_states (
            user_id TEXT PRIMARY KEY,
            state TEXT NOT NULL,
            data_json TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS undo_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            undone INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_undo_user_undone ON undo_actions(user_id, undone, id DESC);
        """,
    ),
]


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def apply_migrations(db_path: str) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, utc_now_iso()),
            )
        conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> Dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def get_entry_by_hash(conn: sqlite3.Connection, user_id: str, text_hash: str) -> Dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM entries WHERE user_id = ? AND text_hash = ?",
        (user_id, text_hash),
    ).fetchone()
    return _row_to_dict(row)


def create_entry(
    conn: sqlite3.Connection,
    user_id: str,
    text: str,
    text_hash: str,
    source: str,
    flags: Dict[str, Any],
) -> Dict[str, Any]:
    created_at = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO entries(user_id, created_at, text, text_hash, source, flags_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, created_at, text, text_hash, source, json_dumps(flags)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_entry(conn: sqlite3.Connection, entry_id: int) -> Dict[str, Any] | None:
    row = conn.execute("SELECT * FROM entries WHERE id = ?", (entry_id,)).fetchone()
    return _row_to_dict(row)


def get_latest_entry_for_user(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM entries WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    return _row_to_dict(row)


def list_user_entries(conn: sqlite3.Connection, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM entries WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def get_next_draft_version(conn: sqlite3.Connection, entry_id: int, platform: str) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS version FROM drafts WHERE entry_id = ? AND platform = ?",
        (entry_id, platform),
    ).fetchone()
    return int(row["version"]) + 1


def create_draft(
    conn: sqlite3.Connection,
    entry_id: int,
    platform: str,
    content: str,
    status: str = "pending",
    scheduled_at: str | None = None,
    meta: Dict[str, Any] | None = None,
    version: int | None = None,
) -> Dict[str, Any]:
    if version is None:
        version = get_next_draft_version(conn, entry_id, platform)
    created_at = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO drafts(entry_id, platform, created_at, content, status, scheduled_at, meta_json, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entry_id, platform, created_at, content, status, scheduled_at, json_dumps(meta), version),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM drafts WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_draft(conn: sqlite3.Connection, draft_id: int) -> Dict[str, Any] | None:
    row = conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    return _row_to_dict(row)


def list_drafts_for_entry(conn: sqlite3.Connection, entry_id: int) -> List[Dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM drafts WHERE entry_id = ? ORDER BY platform, version DESC, id DESC",
        (entry_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_pending_drafts(conn: sqlite3.Connection, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT d.*, e.user_id
        FROM drafts d
        JOIN entries e ON e.id = d.entry_id
        WHERE e.user_id = ? AND d.status = 'pending'
        ORDER BY d.id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_approved_drafts(conn: sqlite3.Connection, user_id: str | None = None) -> List[Dict[str, Any]]:
    if user_id:
        rows = conn.execute(
            """
            SELECT d.*
            FROM drafts d
            JOIN entries e ON e.id = d.entry_id
            WHERE e.user_id = ? AND d.status = 'approved'
            ORDER BY d.id DESC
            """,
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM drafts WHERE status = 'approved' ORDER BY id DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def list_due_scheduled_drafts(conn: sqlite3.Connection, now_iso: str) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM drafts
        WHERE status = 'scheduled' AND scheduled_at IS NOT NULL AND scheduled_at <= ?
        ORDER BY scheduled_at ASC, id ASC
        """,
        (now_iso,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_draft_status(
    conn: sqlite3.Connection,
    draft_id: int,
    status: str,
    scheduled_at: str | None = None,
) -> Dict[str, Any] | None:
    conn.execute(
        "UPDATE drafts SET status = ?, scheduled_at = ? WHERE id = ?",
        (status, scheduled_at, draft_id),
    )
    conn.commit()
    return get_draft(conn, draft_id)


def update_draft_content(
    conn: sqlite3.Connection,
    draft_id: int,
    content: str,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any] | None:
    conn.execute(
        "UPDATE drafts SET content = ?, meta_json = ? WHERE id = ?",
        (content, json_dumps(meta), draft_id),
    )
    conn.commit()
    return get_draft(conn, draft_id)


def create_publish_log(
    conn: sqlite3.Connection,
    draft_id: int,
    platform: str,
    success: bool,
    response: Dict[str, Any] | None,
    error: str | None,
) -> Dict[str, Any]:
    attempted_at = utc_now_iso()
    cur = conn.execute(
        """
        INSERT INTO publish_logs(draft_id, platform, attempted_at, success, response_json, error)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (draft_id, platform, attempted_at, 1 if success else 0, json_dumps(response), error),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM publish_logs WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_last_publish_attempt(conn: sqlite3.Connection) -> Dict[str, Any] | None:
    row = conn.execute("SELECT * FROM publish_logs ORDER BY id DESC LIMIT 1").fetchone()
    return _row_to_dict(row)


def log_llm_call(
    conn: sqlite3.Connection,
    stage: str,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    cur = conn.execute(
        """
        INSERT INTO llm_calls(stage, provider, model, tokens_in, tokens_out, cost_usd, latency_ms, created_at, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            stage,
            provider,
            model,
            tokens_in,
            tokens_out,
            cost_usd,
            latency_ms,
            utc_now_iso(),
            json_dumps(meta),
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM llm_calls WHERE id = ?", (cur.lastrowid,)).fetchone()
    return dict(row)


def get_cost_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS calls,
          COALESCE(SUM(tokens_in), 0) AS tokens_in,
          COALESCE(SUM(tokens_out), 0) AS tokens_out,
          COALESCE(SUM(cost_usd), 0) AS cost_usd
        FROM llm_calls
        """
    ).fetchone()
    return dict(row)


def get_capture_session(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any] | None:
    row = conn.execute("SELECT * FROM sessions WHERE user_id = ?", (user_id,)).fetchone()
    return _row_to_dict(row)


def start_capture_session(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any]:
    existing = get_capture_session(conn, user_id)
    if existing:
        conn.execute(
            "UPDATE sessions SET started_at = ?, buffer_text = '' WHERE user_id = ?",
            (utc_now_iso(), user_id),
        )
    else:
        conn.execute(
            "INSERT INTO sessions(user_id, started_at, buffer_text) VALUES (?, ?, '')",
            (user_id, utc_now_iso()),
        )
    conn.commit()
    return get_capture_session(conn, user_id) or {}


def append_capture_text(conn: sqlite3.Connection, user_id: str, text: str) -> Dict[str, Any] | None:
    existing = get_capture_session(conn, user_id)
    if not existing:
        return None
    combined = existing["buffer_text"]
    if combined:
        combined = f"{combined}\n{text}"
    else:
        combined = text
    conn.execute("UPDATE sessions SET buffer_text = ? WHERE user_id = ?", (combined, user_id))
    conn.commit()
    return get_capture_session(conn, user_id)


def end_capture_session(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any] | None:
    existing = get_capture_session(conn, user_id)
    if not existing:
        return None
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    return existing


def set_user_state(conn: sqlite3.Connection, user_id: str, state: str, data: Dict[str, Any] | None = None) -> None:
    conn.execute(
        """
        INSERT INTO user_states(user_id, state, data_json, updated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET state = excluded.state, data_json = excluded.data_json, updated_at = excluded.updated_at
        """,
        (user_id, state, json_dumps(data), utc_now_iso()),
    )
    conn.commit()


def get_user_state(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any] | None:
    row = conn.execute("SELECT * FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
    return _row_to_dict(row)


def clear_user_state(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
    conn.commit()


def set_global_setting(conn: sqlite3.Connection, key: str, value: Any) -> None:
    row = conn.execute("SELECT preferences_json FROM settings WHERE user_id = '__global__'").fetchone()
    prefs = json_loads(row["preferences_json"]) if row else {}
    prefs[key] = value
    conn.execute(
        """
        INSERT INTO settings(user_id, preferences_json)
        VALUES ('__global__', ?)
        ON CONFLICT(user_id) DO UPDATE SET preferences_json = excluded.preferences_json
        """,
        (json_dumps(prefs),),
    )
    conn.commit()


def get_global_setting(conn: sqlite3.Connection, key: str, default: Any = None) -> Any:
    row = conn.execute("SELECT preferences_json FROM settings WHERE user_id = '__global__'").fetchone()
    if not row:
        return default
    prefs = json_loads(row["preferences_json"])
    return prefs.get(key, default)


def create_undo_action(conn: sqlite3.Connection, user_id: str, action_type: str, payload: Dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO undo_actions(user_id, action_type, payload_json, created_at, undone)
        VALUES (?, ?, ?, ?, 0)
        """,
        (user_id, action_type, json_dumps(payload), utc_now_iso()),
    )
    conn.commit()


def get_last_undo_action(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM undo_actions
        WHERE user_id = ? AND undone = 0
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return _row_to_dict(row)


def mark_undo_action_done(conn: sqlite3.Connection, action_id: int) -> None:
    conn.execute("UPDATE undo_actions SET undone = 1 WHERE id = ?", (action_id,))
    conn.commit()


def delete_entry(conn: sqlite3.Connection, entry_id: int) -> None:
    conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
    conn.commit()


def delete_draft(conn: sqlite3.Connection, draft_id: int) -> None:
    conn.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
    conn.commit()
