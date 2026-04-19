def test_search_people(tools, fake_li):
    hits = tools["search_people"](keywords="founder", limit=5)
    assert hits and hits[0]["public_id"] == "jane-doe"
    assert any(c[0] == "search_people" for c in fake_li.calls)


def test_get_profile(tools):
    p = tools["get_profile"](public_id="jane-doe")
    assert p["firstName"] == "Jane"


def test_get_profile_requires_id(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["get_profile"]()


def test_companies(tools):
    cos = tools["search_companies"](keywords=["saas"])
    assert cos[0]["public_id"] == "acme"
    assert tools["get_company"]("acme")["staffCount"] == 120
