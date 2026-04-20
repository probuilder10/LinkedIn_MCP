import json
from io import StringIO
from unittest.mock import patch


def run_admin(argv: list[str]) -> str:
    from linkedin_mcp.admin import main

    buf = StringIO()
    with patch("sys.stdout", buf):
        rc = main(argv)
    assert rc == 0, f"admin command {argv} returned {rc}"
    return buf.getvalue()


def test_quota_cmd(tools):
    out = run_admin(["quota"])
    data = json.loads(out)
    assert data["limits"]["messages"] > 0


def test_campaigns_list(tools):
    tools["create_icp"](name="i", description="")
    tools["create_campaign"](name="c1", icp_name="i", connection_template="hi")
    out = run_admin(["campaigns", "list"])
    data = json.loads(out)
    assert any(r["name"] == "c1" for r in data)


def test_prospects_list(tools):
    tools["create_icp"](name="i", description="", titles=["VP Sales"])
    tools["score_prospect"]("jane-doe", "i")
    out = run_admin(["prospects", "list", "--icp", "i", "--min-score", "0"])
    data = json.loads(out)
    assert any(r["public_id"] == "jane-doe" for r in data)


def test_db_reset(tools):
    from linkedin_mcp import config

    tools["list_icps"]()  # force DB creation
    p = config.settings.linkedin_mcp_db
    assert p.exists()
    run_admin(["db", "reset"])
    assert not p.exists()
