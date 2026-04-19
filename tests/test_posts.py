from datetime import datetime, timedelta, timezone


def test_schedule_list_cancel(tools):
    when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    p = tools["schedule_post"]("Hello world", when)
    assert p["status"] == "scheduled"
    pid = p["id"]

    all_posts = tools["list_scheduled_posts"](status="scheduled")
    assert any(x["id"] == pid for x in all_posts)

    cancelled = tools["cancel_scheduled_post"](pid)
    assert cancelled["status"] == "cancelled"


def test_publish_post(tools, fake_li):
    res = tools["publish_post"]("hi world")
    assert res["ok"] is True
    assert any(c[0] == "_post" and c[1]["uri"].endswith("/normShares") for c in fake_li.calls)


def test_schedule_post_rejects_bad_iso(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["schedule_post"]("x", "not-a-date")
