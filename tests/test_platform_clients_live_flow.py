import types

from telegram_social_agent.platform_clients.linkedin_client import LinkedInClient
from telegram_social_agent.platform_clients.threads_client import ThreadsClient


class DummyResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_linkedin_accepts_person_urn_2(monkeypatch):
    monkeypatch.setenv("LINKEDIN_ACCESS_TOKEN", "token")
    monkeypatch.delenv("LINKEDIN_PERSON_URN", raising=False)
    monkeypatch.setenv("LINKEDIN_PERSON_URN_2", "abc123")

    def fake_post(url, json, headers, timeout):
        assert json["author"] == "urn:li:person:abc123"
        return DummyResponse(status_code=201, payload={"id": "ok"}, text='{"id":"ok"}')

    monkeypatch.setattr("telegram_social_agent.platform_clients.linkedin_client.requests.post", fake_post)

    result = LinkedInClient().publish("hello", dry_run=False)
    assert result["success"] is True
    assert result["author"] == "urn:li:person:abc123"


def test_threads_uses_create_then_publish(monkeypatch):
    monkeypatch.setenv("THREADS_USER_ID", "u1")
    monkeypatch.setenv("THREADS_ACCESS_TOKEN", "t1")

    calls = []

    def fake_post(url, data, timeout):
        calls.append((url, data))
        if url.endswith("/threads"):
            assert data["media_type"] == "TEXT"
            return DummyResponse(status_code=200, payload={"id": "creation123"}, text='{"id":"creation123"}')
        if url.endswith("/threads_publish"):
            assert data["creation_id"] == "creation123"
            return DummyResponse(status_code=200, payload={"id": "thread456"}, text='{"id":"thread456"}')
        return DummyResponse(status_code=404, payload={}, text="not found")

    monkeypatch.setattr("telegram_social_agent.platform_clients.threads_client.requests.post", fake_post)

    result = ThreadsClient().publish("hello", dry_run=False)
    assert result["success"] is True
    assert len(calls) == 2
