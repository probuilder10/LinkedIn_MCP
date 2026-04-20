from unittest.mock import MagicMock, patch


def test_notify_noop_without_url():
    from linkedin_mcp.notify import notify

    assert notify("job_change", {"x": 1}) is False


def test_notify_posts_when_url_set():
    from linkedin_mcp import config, notify as nmod

    config.settings.notify_webhook_url = "https://example.test/hook"
    try:
        with patch.object(nmod.httpx, "post", MagicMock()) as m:
            assert nmod.notify("job_change", {"name": "Jane", "to": {"title": "VP", "company": "Acme"}}) is True
            assert m.called
            kwargs = m.call_args.kwargs
            assert kwargs["json"]["event"] == "job_change"
            assert "Jane" in kwargs["json"]["text"]
    finally:
        config.settings.notify_webhook_url = ""
