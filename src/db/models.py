# src/db/models.py


"""
Database models and helpers for the agentic social diary project.

This module is responsible for:
- Getting a connection to the SQLite database,
- Creating tables if they do not exist yet,
- Providing tiny helper functions that higher-level "data tools" will use.

keeping SQL very explicit and simple on purpose so it's easy to understand.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from ..core.config_loader import get_config

def _get_db_path() -> Path:
    """
    Determine the SQLite database file path based on configuration.

    We read:
    - config['database']['url']  (may be overridden by DATABASE_URL env variable)

    For simplicity, we treat this 'url' as a file path.
    If someone passes 'sqlite:///agent_posts.db', we strip the prefix.

    Returns:
        A Path object pointing to the SQLite file.
    """
    cfg = get_config()
    db_cfg = cfg.get("database", {})
    url = db_cfg.get("url", "agent_posts.db")

    prefix = "sqlite:///"
    if url.startswith(prefix):
        url = url[len(prefix):]
    
    db_path = Path(url)
    return db_path

def get_connection() -> sqlite3.Connection:
    """
    Open a connection to the SQLite database.

    The connection:
    - Creates the file if it does not exist,
    - Should be closed by the caller when done.

    Returns:
        An active sqlite3.Connection object.
    """
    db_path = _get_db_path()
    conn = sqlite3.connect(db_path)
    return conn

def init_db() -> None:
    """
    Initialize the database by creating all required tables if they do not exist.

    We create:
    - diaries
    - posts
    - publish_logs
    - cost_logs

    This function is safe to call multiple times; it uses CREATE TABLE IF NOT EXISTS.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Table: diaries
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS diaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,        -- e.g. 'diary_file' or 'x_threads_file'
            raw_text TEXT NOT NULL,
            text_hash TEXT NOT NULL
        )
        """
    )
    # Table: posts
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diary_id INTEGER NOT NULL,   -- references diaries.id
            platform TEXT NOT NULL,      -- 'x', 'threads', 'linkedin', etc.
            content TEXT NOT NULL,
            status TEXT NOT NULL,        -- 'draft' or 'published'
            created_at TEXT NOT NULL,
            FOREIGN KEY (diary_id) REFERENCES diaries (id)
        )
        """
    )
    # Table: publish_logs
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS publish_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,    -- references posts.id
            platform TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            success INTEGER NOT NULL,    -- 1 for success, 0 for failure
            api_response_excerpt TEXT,   -- optional short snippet of API response
            FOREIGN KEY (post_id) REFERENCES posts (id)
        )
        """
    )
    # Table: cost_logs
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cost_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            model TEXT NOT NULL,
            tokens_in INTEGER NOT NULL,
            tokens_out INTEGER NOT NULL,
            estimated_cost REAL NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()

def utc_now_iso() -> str:
    """
    Get the current UTC time as an ISO 8601 string.

    Example: '2025-11-17T15:23:45Z'

    Returns:
        ISO 8601 formatted datetime string in UTC.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")