from telegram_social_agent.llm.providers.gemini_provider import GeminiProvider


def test_gemini_uses_google_api_key_alias(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")

    provider = GeminiProvider()
    assert provider._api_key == "test-key"
