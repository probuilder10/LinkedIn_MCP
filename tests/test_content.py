def test_draft_post_fallback(tools):
    out = tools["draft_post"](topic="sales enablement", format_style="listicle")
    assert out["source"].startswith("fallback")
    assert "sales enablement" in out["text"]


def test_react_to_post(tools, fake_li):
    res = tools["react_to_post"]("urn:li:activity:p1", "PRAISE")
    assert res["ok"] is True
    call = [c for c in fake_li.calls if c[0] == "react_to_post"][0][1]
    assert call["reaction_type"] == "PRAISE"


def test_react_invalid(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["react_to_post"]("urn:li:activity:p1", "ROFL")


def test_profile_views(tools):
    pv = tools["profile_views"]()
    assert pv["numViews"] == 17
