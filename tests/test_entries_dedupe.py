from telegram_social_agent.config import load_settings
from telegram_social_agent.models import apply_migrations, get_connection
from telegram_social_agent.orchestrator import ingest_entry


def test_entry_dedupe_is_per_user(tmp_path):
    db_path = str(tmp_path / "app.db")
    apply_migrations(db_path)
    cfg = load_settings()

    with get_connection(db_path) as conn:
        first = ingest_entry(conn, user_id="u1", entry_text="  Hello   World  ", flags={})
        second = ingest_entry(conn, user_id="u1", entry_text="hello world", flags={})
        third = ingest_entry(conn, user_id="u2", entry_text="hello world", flags={})

    assert first["ok"] is True
    assert second["ok"] is False
    assert second["reason"] == "duplicate"
    assert third["ok"] is True
