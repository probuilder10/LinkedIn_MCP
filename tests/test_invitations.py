def test_list_invitations(tools):
    out = tools["list_invitations"]()
    assert len(out) == 3
    assert out[0]["entityUrn"].startswith("urn:li:invitation:")


def test_respond_invitation(tools, fake_li):
    res = tools["respond_invitation"]("urn:li:invitation:1", "s1", "accept")
    assert res["ok"] is True
    assert res["action"] == "accept"
    assert any(c[0] == "reply_invitation" for c in fake_li.calls)


def test_respond_invitation_bad_action(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["respond_invitation"]("u", "s", "maybe")


def test_bulk_accept_filters_spam(tools):
    """With heuristic on, invitation #2 (no note, no insights) should be skipped."""
    res = tools["bulk_accept_invitations"](max_count=10, only_first_degree_hints=True)
    assert res["accepted"] == 2  # #1 has customMessage, #3 has mutualCurrentCompany
    assert res["skipped"] == 1


def test_bulk_accept_all(tools):
    res = tools["bulk_accept_invitations"](max_count=10, only_first_degree_hints=False)
    assert res["accepted"] == 3


def test_follow_company(tools, fake_li):
    tools["follow_company"]("urn:li:fs_followingInfo:x")
    assert any(c[0] == "follow_company" for c in fake_li.calls)


def test_remove_connection(tools, fake_li):
    res = tools["remove_connection"]("jane-doe")
    assert res["ok"] is True
