def test_list_unread(tools):
    out = tools["list_unread"]()
    # 3 unread convos, conversation c4 is read
    assert len(out) == 3
    urns = {c["conversation_urn_id"] for c in out}
    assert urns == {"c1", "c2", "c3"}


def test_triage_inbox_classifies(tools):
    res = tools["triage_inbox"]()
    assert res["total_unread"] == 3
    assert res["counts"]["schedule_call"] >= 1  # c1: "15-min chat"
    assert res["counts"]["spam"] >= 1  # c2: "free trial"
    assert res["counts"]["reply"] >= 1  # c3: generic


def test_draft_reply_fallback(tools):
    r = tools["draft_reply"]("urn:li:fs_conversation:c1", goal="book a demo")
    assert r["source"].startswith("fallback")
    assert "book a demo" in r["body"]


def test_bulk_reply_dry_run(tools, fake_li):
    drafts = [
        {"conversation_urn_id": "urn:li:fs_conversation:c1", "body": "Sounds good"},
        {"conversation_urn_id": "urn:li:fs_conversation:c3", "body": "Thanks!"},
    ]
    res = tools["bulk_reply"](drafts=drafts, dry_run=True)
    assert res["sent"] == 0
    assert len(res["results"]) == 2
    # No real send should have happened
    assert not any(c[0] == "send_message" for c in fake_li.calls)


def test_bulk_reply_live(tools, fake_li):
    drafts = [{"conversation_urn_id": "urn:li:fs_conversation:c1", "body": "ok"}]
    res = tools["bulk_reply"](drafts=drafts, dry_run=False)
    assert res["sent"] == 1
    assert any(c[0] == "send_message" for c in fake_li.calls)
