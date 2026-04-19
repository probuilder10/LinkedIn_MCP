def test_full_campaign_flow(tools, fake_li):
    tools["create_icp"](name="icp", description="x", titles=["VP Sales"])
    tools["score_prospect"]("jane-doe", "icp")

    camp = tools["create_campaign"](
        name="apr",
        icp_name="icp",
        connection_template="Hi {name}",
        followup_templates=[
            {"delay_hours": 0, "body": "{name} — follow up 1"},
            {"delay_hours": 0, "body": "{name} — follow up 2"},
        ],
    )
    assert camp["name"] == "apr"

    enrolled = tools["enroll_prospects"]("apr", ["jane-doe"])
    assert enrolled["enrolled"] == 1

    tools["start_campaign"]("apr")
    tick = tools["run_campaign_tick"]("apr")
    assert tick["attempted"] >= 1

    # Second tick should send first follow-up (delay_hours=0)
    tools["run_campaign_tick"]("apr")

    metrics = tools["campaign_metrics"]("apr")
    assert metrics["matrix"]["connect"]["sent"] == 1


def test_enroll_unknown_campaign_raises(tools):
    import pytest

    with pytest.raises(ValueError):
        tools["enroll_prospects"]("ghost", ["jane-doe"])


def test_pause_campaign(tools):
    tools["create_icp"](name="i", description="")
    tools["create_campaign"](name="p", icp_name="i", connection_template="hi")
    tools["pause_campaign"]("p")
    camps = tools["list_campaigns"]()
    assert [c for c in camps if c["name"] == "p"][0]["status"] == "paused"
