from telegram_social_agent.platform_clients.linkedin_client import LinkedInClient
from telegram_social_agent.platform_clients.threads_client import ThreadsClient
from telegram_social_agent.platform_clients.x_client import XClient


def test_platform_clients_support_dry_run():
    x = XClient().publish("hello", dry_run=True)
    th = ThreadsClient().publish("hello", dry_run=True)
    li = LinkedInClient().publish("hello", dry_run=True)

    assert x["success"] is True and x["platform"] == "x"
    assert th["success"] is True and th["platform"] == "threads"
    assert li["success"] is True and li["platform"] == "linkedin"
