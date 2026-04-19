def test_create_and_score(tools):
    icp = tools["create_icp"](
        name="saas_founders",
        description="SaaS founders",
        titles=["VP Sales", "Head of Revenue"],
        seniorities=["vp"],
        industries=["Software Development"],
        geographies=["United States"],
        keywords=["SaaS", "B2B"],
    )
    assert icp["id"] > 0

    res = tools["score_prospect"]("jane-doe", "saas_founders")
    assert 0 <= res["score"] <= 100
    assert res["score"] >= 60, f"Jane should match strongly, got {res['score']}"

    listed = tools["list_prospects"](icp_name="saas_founders", min_score=50)
    assert listed and listed[0]["public_id"] == "jane-doe"


def test_score_unknown_icp(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["score_prospect"]("jane-doe", "missing")


def test_list_icps(tools):
    tools["create_icp"](name="a", description="x")
    icps = tools["list_icps"]()
    assert any(i["name"] == "a" for i in icps)
