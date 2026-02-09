from telegram_social_agent.llm.types import ProviderError
from telegram_social_agent.models import apply_migrations, get_connection
from telegram_social_agent.orchestrator import generate_drafts, ingest_entry


class AlwaysFailRouter:
    def generate(self, *args, **kwargs):
        raise ProviderError("all providers failed")


def test_generate_drafts_falls_back_when_all_llms_fail(tmp_path):
    db_path = str(tmp_path / "app.db")
    apply_migrations(db_path)

    config = {
        "modes": {"llm_enabled": True},
        "platform_limits": {"x_max_chars": 280, "threads_max_chars": 500, "linkedin_max_chars": 3000},
        "platforms": {"x_enabled": True, "threads_enabled": True, "linkedin_enabled": True},
    }
    style_context = {
        "contract": "concise",
        "templates": {
            "x": "{summary}",
            "threads": "{summary}",
            "linkedin": "{summary}",
        },
    }

    with get_connection(db_path) as conn:
        entry_res = ingest_entry(
            conn,
            user_id="u1",
            entry_text="Today I built something useful and learned from shipping fast.",
            flags={"draft": True},
        )
        assert entry_res["ok"] is True

        result = generate_drafts(
            conn,
            config,
            router=AlwaysFailRouter(),
            style_context=style_context,
            entry_id=entry_res["entry"]["id"],
            platforms=["linkedin"],
            is_strict=False,
        )

    assert result["ok"] is True
    assert len(result["drafts"]) == 1
    draft = result["drafts"][0]["draft"]
    assert draft["platform"] == "linkedin"
    assert draft["status"] == "pending"
    assert len(draft["content"]) > 0
