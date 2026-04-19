def test_list_connections(tools, fake_li):
    conns = tools["list_connections"]()
    assert conns[0]["public_id"] == "jane-doe"
    # Should have fetched the user profile to resolve our own urn id
    assert any(c[0] == "get_user_profile" for c in fake_li.calls)


def test_send_connection_request(tools, fake_li):
    res = tools["send_connection_request"]("jane-doe", message="hi")
    assert res["ok"] is True
    assert any(c[0] == "add_connection" for c in fake_li.calls)


def test_send_connection_note_limit(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["send_connection_request"]("jane-doe", message="x" * 301)


def test_send_message_by_conversation(tools, fake_li):
    res = tools["send_message"](body="hello", conversation_urn_id="urn:li:fs_conversation:c1")
    assert res["ok"] is True


def test_send_message_resolves_public_ids(tools, fake_li):
    tools["send_message"](body="hello", recipient_public_ids=["jane-doe"])
    sm = [c for c in fake_li.calls if c[0] == "send_message"][0][1]
    assert sm["recipients"] == ["jane-doe"]  # resolved from fake get_profile entityUrn


def test_send_message_requires_target(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["send_message"](body="hi")


def test_draft_message_fallback(tools):
    out = tools["draft_personalized_message"]("jane-doe", goal="book a call")
    assert "Jane" in out["body"] and out["source"].startswith("fallback")
