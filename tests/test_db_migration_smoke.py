from telegram_social_agent.models import apply_migrations, get_connection


REQUIRED_TABLES = {
    "schema_migrations",
    "entries",
    "drafts",
    "publish_logs",
    "llm_calls",
    "sessions",
    "settings",
    "user_states",
    "undo_actions",
}


def test_db_migrations_are_idempotent(tmp_path):
    db_path = str(tmp_path / "app.db")
    apply_migrations(db_path)
    apply_migrations(db_path)

    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        tables = {row["name"] for row in rows}

    assert REQUIRED_TABLES.issubset(tables)
