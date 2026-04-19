import pytest

from linkedin_mcp.client import LinkedInRateLimitError


def test_whoami(tools):
    me = tools["whoami"]()
    assert me["public_id"] == "me"


def test_quota_status(tools):
    q = tools["quota_status"]()
    assert q["limits"]["messages"] > 0
    assert q["today"]["messages"] == 0


def test_quota_enforced(tools):
    from linkedin_mcp import config

    config.settings.max_connection_requests_per_day = 1

    tools["send_connection_request"]("jane-doe")
    with pytest.raises(LinkedInRateLimitError):
        tools["send_connection_request"]("jane-doe")
