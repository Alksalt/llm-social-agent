# src/tools/data_tools.py

"""
Data and logging tools.

These functions provide a clean interface for:
- Storing diary entries,
- Checking if a diary entry is new or a duplicate,
- Storing post drafts,
- (Later) logging publishing results and cost information.

They sit on top of the low-level SQLite helpers in db.models
and hide raw SQL from the rest of the codebase.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import sqlite3                    
from typing import Optional, Dict, Any, List

from ..db.models import get_connection, utc_now_iso  # DB connection + timestamp helper

def _hash_text(text: str) -> str: 
    """
    Compute a stable hash of the given text.

    We use SHA-256 to:
    - Detect if a diary entry is exactly the same as a previous one,
    - Avoid reprocessing the same diary multiple times.

    Args:
        text:
            Text to hash.

    Returns:
        Hexadecimal string representation of the hash.
    """
    normalized = text.strip().encode("utf-8")
    digest = hashlib.sha256(normalized).hexdigest()
    return digest
def is_new_diary_entry(raw_text: str, source: str = "diary_file") -> bool:
    """
    Check whether the given diary text is new for the specified source.

    We do this by:
    - Computing the hash of the text,
    - Checking if there is already a diary row with the same hash and source.

    Args:
        raw_text:
            The diary text to check.
        source:
            Where this diary comes from (e.g. 'diary_file', 'x_threads_file').

    Returns:
        True if this text has NOT been seen before for this source.
        False if an identical entry already exists.
        """
    text_hash = _hash_text(raw_text)
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id FROM diaries
        WHERE source = ? AND text_hash = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (source, text_hash)
    )
    row = cur.fetchone()
    conn.close()
    return row is None

def store_diary_entry(raw_text: str, source: str = "diary_file") -> int:
    """
    Store a diary entry in the 'diaries' table.

    Args:
        raw_text:
            Diary text to store.
        source:
            Source label (e.g. 'diary_file', 'x_threads_file').

    Returns:
        The ID (primary key) of the inserted diary row.
    """
    text_hash = _hash_text(raw_text)
    created_at = utc_now_iso()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO diaries(created_at, source, raw_text, text_hash)
        VALUES (?, ?, ?, ?)
        """,
        (created_at, source, raw_text, text_hash)
    )
    diary_id = cur.lastrowid
    conn.commit()
    conn.close()

    return diary_id

def store_post_draft(
        diary_id: int,
        platform: str,
        content: str,
        status: str = "draft",
) -> int:
    """
    Store a post draft in the 'posts' table.

    Args:
        diary_id:
            ID of the related diary entry (from store_diary_entry()).
        platform:
            Platform code, e.g. 'x', 'threads', 'linkedin'.
        content:
            Post content (already generated text).
        status:
            'draft' or 'published'. Defaults to 'draft'.

    Returns:
        The ID of the inserted post row.
    """
    created_at = utc_now_iso()
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO posts (diary_id, platform, content, status, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (diary_id, platform, content, status, created_at)
    )
    post_id = cur.lastrowid
    conn.commit()
    conn.close()

    return post_id

def log_publish_result(
        post_id: int,
        platform: str,
        success: bool,
        api_response_excerpt: str | None = None
) -> int:
    """
    Log the result of a publishing attempt into the 'publish_logs' table.

    Args:
        post_id:
            ID of the post in our 'posts' table.
        platform:
            'x', 'threads', 'linkedin', etc.
        success:
            True if publishing succeeded, False otherwise.
        api_response_excerpt:
            Optional short snippet of the API response or error message.

    Returns:
        ID of the inserted publish_logs row.
    """
    timestamp = utc_now_iso()
    success_int = 1 if success else 0

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO publish_logs (post_id, platform, timestamp, success, api_response_excerpt)
        VALUES (?, ?, ?, ?, ?)
        """,
        (post_id, platform, timestamp, success_int, api_response_excerpt),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()

    return row_id

def count_linkedin_publishes_last_days(days: int = 7) -> int:
    """
    Count how many successful LinkedIn publishes happened in the last `days` days.

    We use the 'publish_logs' table where:
    - platform = 'linkedin'
    - success = 1
    - timestamp >= (now_utc - days)

    Args:
        days:
            Rolling window size in days (default: 7).

    Returns:
        Number of successful LinkedIn publishes in that window.
    """
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT COUNT(*)
        FROM publish_logs
        WHERE platform = 'linkedin'
          AND success = 1
          AND timestamp >= ?
        """,
        (cutoff_iso,)
    )
    (count, ) = cur.fetchone()
    conn.close()

    return int(count)
def get_pending_drafts(allowed_diary_ids: list[int] | None = None) -> list[dict]:
    """
    Fetch posts with status='draft'.

    If allowed_diary_ids is provided, only return posts whose diary_id is in that list.
    These are used by the review step, where you decide which drafts to approve.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if allowed_diary_ids is not None:
        if not allowed_diary_ids:
            conn.close()
            return []
        placeholders = ",".join("?" for _ in allowed_diary_ids)
        query = f"""
            SELECT id, diary_id, platform, content, status, created_at
            FROM posts
            WHERE status = 'draft'
              AND diary_id IN ({placeholders})
            ORDER BY created_at ASC
        """
        cur.execute(query, allowed_diary_ids)
    else:
        cur.execute(
            """
            SELECT id, diary_id, platform, content, status, created_at
            FROM posts
            WHERE status = 'draft'
            ORDER BY created_at ASC
            """
        )

    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_approved_posts(allowed_diary_ids: list[int] | None = None) -> list[dict]:
    """
    Fetch posts with status='approved'.

    If allowed_diary_ids is provided, only return posts whose diary_id is in that list.
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if allowed_diary_ids is not None:
        if not allowed_diary_ids:
            conn.close()
            return []
        placeholders = ",".join("?" for _ in allowed_diary_ids)
        query = f"""
            SELECT id, diary_id, platform, content, status, created_at
            FROM posts
            WHERE status = 'approved'
              AND diary_id IN ({placeholders})
            ORDER BY created_at ASC
        """
        cur.execute(query, allowed_diary_ids)
    else:
        cur.execute(
            """
            SELECT id, diary_id, platform, content, status, created_at
            FROM posts
            WHERE status = 'approved'
            ORDER BY created_at ASC
            """
        )
    rows = cur.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def set_post_status(post_id: int, status: str) -> None:
    """
    Update the 'status' of a post in the posts table.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE posts
        SET status = ?
        WHERE id = ?
        """,
        (status, post_id),
    )

    conn.commit()
    conn.close()

def mark_post_as_published(post_id: int) -> None:
    """
    Update a post's status to 'published' in the 'posts' table.

    Args:
        post_id:
            Primary key of the post in 'posts' table.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE posts
        SET status = 'published'
        WHERE id = ?
        """,
        (post_id, )
    )
    conn.commit()
    conn.close()
    
def log_cost_entry(
    model: str,
    tokens_in: int,
    tokens_out: int,
    estimated_cost: float,
    timestamp_iso: Optional[str] = None,
) -> int:
    """
    Store a single LLM usage/cost entry in the cost_logs table.
    Args:
        model:
            Model name used for this call (e.g. 'gpt-5-mini').
        tokens_in:
            Number of input tokens reported by the API.
        tokens_out:
            Number of output tokens reported by the API.
        estimated_cost:
            Estimated cost in USD for this call.
        timestamp_iso:
            Optional ISO timestamp string. If None, uses utc_now_iso().

    Returns:
        The ID of the inserted cost_logs row.
    """
    if timestamp_iso is None:
        timestamp_iso = utc_now_iso()

    conn = get_connection()
    cur = conn.cursor()
    
    cur.execute(
        """
        INSERT INTO cost_logs (timestamp, model, tokens_in, tokens_out, estimated_cost)
        VALUES (?, ?, ?, ?, ?)
        """,
        (timestamp_iso, model, tokens_in, tokens_out, float(estimated_cost)),
    )

    row_id = cur.lastrowid
    conn.commit()
    conn.close()

    return row_id

def summarize_costs() -> dict:
    """
    Summarize total and per-model cost from the cost_logs table.

    Returns:
        {
            "total_cost": float,
            "by_model": {
                "gpt-5-mini": {
                    "cost": float,
                    "calls": int,
                    "tokens_in": int,
                    "tokens_out": int,
                },
                ...
            }
        }
    """
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT model,
               COUNT(*) AS calls,
               SUM(tokens_in) AS sum_in,
               SUM(tokens_out) AS sum_out,
               SUM(estimated_cost) AS sum_cost
        FROM cost_logs
        GROUP BY model
        """
    )

    rows = cur.fetchall()
    conn.close()

    total_cost = 0.0
    by_model: dict[str, dict[str, Any]] = {}

    for row in rows:
        model = row["model"]
        calls = int(row["calls"])
        tokens_in = int(row["sum_in"] or 0)
        tokens_out = int(row["sum_out"] or 0)
        cost = float(row["sum_cost"] or 0.0)

        total_cost += cost
        by_model[model] = {
            "cost": cost,
            "calls": calls,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    return {
        "total_cost": total_cost,
        "by_model": by_model,
    }
    
