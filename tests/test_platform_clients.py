"""
Tests for platform client adapters (X, Threads, LinkedIn).

These focus on dry-run behavior (no network) and the config-error paths
when required environment variables are missing.
"""
import os

from src.platform_clients.x_client import publish_x_post
from src.platform_clients.threads_client import publish_threads_post
from src.platform_clients.linkedin_client import publish_linkedin_post


def _clear_env(monkeypatch, keys: list[str]) -> None:
    """Remove environment variables if present."""
    for key in keys:
        monkeypatch.delenv(key, raising=False)


def test_publish_x_post_dry_run_ok():
    result = publish_x_post("hello x", dry_run=True)
    assert result["ok"] is True
    assert result["platform"] == "x"
    assert result["dry_run"] is True


def test_publish_x_post_missing_env_real_mode_returns_config_error(monkeypatch):
    _clear_env(
        monkeypatch,
        ["X_API_KEY", "X_API_KEY_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET"],
    )
    result = publish_x_post("hello x", dry_run=False)
    assert result["ok"] is False
    assert result["dry_run"] is False
    assert isinstance(result["error"], str)
    assert result["error"].startswith("config_error")


def test_publish_threads_post_dry_run_ok():
    result = publish_threads_post("hello threads", dry_run=True)
    assert result["ok"] is True
    assert result["platform"] == "threads"
    assert result["dry_run"] is True


def test_publish_threads_post_missing_env_real_mode_returns_config_error(monkeypatch):
    _clear_env(monkeypatch, ["THREADS_USER_ID", "THREADS_ACCESS_TOKEN"])
    result = publish_threads_post("hello threads", dry_run=False)
    assert result["ok"] is False
    assert result["dry_run"] is False
    assert isinstance(result["error"], str)
    assert result["error"].startswith("config_error")


def test_publish_linkedin_post_dry_run_ok():
    result = publish_linkedin_post("hello linkedin", dry_run=True)
    assert result["ok"] is True
    assert result["platform"] == "linkedin"
    assert result["dry_run"] is True


def test_publish_linkedin_post_missing_env_real_mode_returns_config_error(monkeypatch):
    _clear_env(monkeypatch, ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_PERSON_URN"])
    result = publish_linkedin_post("hello linkedin", dry_run=False)
    assert result["ok"] is False
    assert result["dry_run"] is False
    assert isinstance(result["error"], str)
    assert result["error"].startswith("config_error")
