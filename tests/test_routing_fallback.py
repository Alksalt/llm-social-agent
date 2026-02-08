from telegram_social_agent.llm.router import LLMRouter
from telegram_social_agent.llm.types import LLMResult, ProviderError
from telegram_social_agent.models import apply_migrations, get_connection


class FailingProvider:
    name = "fail"

    def generate(self, request):
        raise ProviderError("simulated failure")


class SuccessProvider:
    name = "ok"

    def generate(self, request):
        return LLMResult(
            text="success",
            provider="ok",
            model=request.model,
            tokens_in=10,
            tokens_out=5,
            latency_ms=20,
        )


def test_router_fallback_uses_next_provider(tmp_path):
    db_path = str(tmp_path / "app.db")
    apply_migrations(db_path)

    config = {
        "llm": {"temperature": 0.1, "max_tokens": 64, "timeout_seconds": 5},
        "routing": {"summarize": ["fail:model-a", "ok:model-b"]},
        "pricing": {"ok:model-b": {"input_per_1k": 0.001, "output_per_1k": 0.002}},
    }

    with get_connection(db_path) as conn:
        router = LLMRouter(
            config=config,
            conn=conn,
            providers={"fail": FailingProvider(), "ok": SuccessProvider()},
        )
        result = router.generate("summarize", prompt="p", system="s")

        assert result.text == "success"
        row = conn.execute("SELECT COUNT(*) AS n FROM llm_calls").fetchone()
        assert row["n"] == 1
