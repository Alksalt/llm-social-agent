from telegram_social_agent.validators import truncate_to_limit, validate_draft


def test_truncation_and_validation_logic():
    cfg = {"platform_limits": {"x_max_chars": 10, "threads_max_chars": 500, "linkedin_max_chars": 3000}}
    content = "0123456789012345"

    truncated = truncate_to_limit(content, 10)
    assert len(truncated) <= 10
    assert truncated.endswith("...")

    v1 = validate_draft("x", content, cfg)
    v2 = validate_draft("x", truncated, cfg)

    assert v1["ok"] is False
    assert v2["ok"] is True
