"""Multi-step outreach campaigns: connect -> wait -> follow-up(s)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..storage.db import as_dict, as_list, get_db, jdump, jload


def register(mcp) -> None:
    @mcp.tool()
    def create_campaign(
        name: str,
        icp_name: str,
        connection_template: str,
        followup_templates: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Create a campaign.

        followup_templates: [{"delay_hours": 48, "body": "..."}, ...]
        """
        db = get_db()
        icp = db.execute("SELECT id FROM icp WHERE name=?", (icp_name,)).fetchone()
        if not icp:
            raise ValueError(f"ICP '{icp_name}' not found")
        db.execute(
            "INSERT INTO campaigns(name, icp_id, connection_template, followup_templates) "
            "VALUES(?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET connection_template=excluded.connection_template, "
            "followup_templates=excluded.followup_templates, icp_id=excluded.icp_id",
            (name, icp["id"], connection_template, jdump(followup_templates or [])),
        )
        row = db.execute("SELECT * FROM campaigns WHERE name=?", (name,)).fetchone()
        out = as_dict(row) or {}
        out["followup_templates"] = jload(out.get("followup_templates"))
        return out

    @mcp.tool()
    def enroll_prospects(campaign_name: str, public_ids: list[str]) -> dict[str, Any]:
        """Enroll prospects into a campaign. Only already-scored prospects are eligible."""
        db = get_db()
        camp = db.execute("SELECT * FROM campaigns WHERE name=?", (campaign_name,)).fetchone()
        if not camp:
            raise ValueError(f"campaign '{campaign_name}' not found")
        enrolled = 0
        for pid in public_ids:
            p = db.execute("SELECT id FROM prospects WHERE public_id=?", (pid,)).fetchone()
            if not p:
                continue
            db.execute(
                "INSERT OR IGNORE INTO campaign_steps(campaign_id, prospect_id, step, status, run_after) "
                "VALUES(?,?,?,?,?)",
                (
                    camp["id"],
                    p["id"],
                    "connect",
                    "pending",
                    datetime.utcnow().isoformat(),
                ),
            )
            enrolled += 1
        return {"campaign": campaign_name, "enrolled": enrolled}

    @mcp.tool()
    def start_campaign(name: str) -> dict[str, Any]:
        db = get_db()
        db.execute("UPDATE campaigns SET status='active' WHERE name=?", (name,))
        return as_dict(db.execute("SELECT * FROM campaigns WHERE name=?", (name,)).fetchone())

    @mcp.tool()
    def pause_campaign(name: str) -> dict[str, Any]:
        db = get_db()
        db.execute("UPDATE campaigns SET status='paused' WHERE name=?", (name,))
        return as_dict(db.execute("SELECT * FROM campaigns WHERE name=?", (name,)).fetchone())

    @mcp.tool()
    def campaign_metrics(name: str) -> dict[str, Any]:
        """Return counts per step/status + reply/conversion rates."""
        db = get_db()
        camp = db.execute("SELECT * FROM campaigns WHERE name=?", (name,)).fetchone()
        if not camp:
            raise ValueError(f"campaign '{name}' not found")
        rows = db.execute(
            "SELECT step, status, COUNT(*) c FROM campaign_steps WHERE campaign_id=? GROUP BY step, status",
            (camp["id"],),
        ).fetchall()
        matrix: dict[str, dict[str, int]] = {}
        for r in rows:
            matrix.setdefault(r["step"], {})[r["status"]] = r["c"]
        total_connects = sum(matrix.get("connect", {}).values())
        connected = matrix.get("connect", {}).get("sent", 0)
        replies = sum(
            v for k, m in matrix.items() if k.startswith("followup") for s, v in m.items() if s == "sent"
        )
        return {
            "campaign": name,
            "status": camp["status"],
            "matrix": matrix,
            "connect_rate": round(connected / total_connects, 3) if total_connects else 0,
            "followups_sent": replies,
        }

    @mcp.tool()
    def run_campaign_tick(name: str, max_actions: int = 20) -> dict[str, Any]:
        """Process due steps for a campaign (call this from an external scheduler or manually).
        Returns how many actions were attempted."""
        from ..client import LinkedInClient

        db = get_db()
        camp = db.execute("SELECT * FROM campaigns WHERE name=?", (name,)).fetchone()
        if not camp or camp["status"] != "active":
            return {"campaign": name, "attempted": 0, "note": "not active"}

        followups = jload(camp["followup_templates"]) or []
        now = datetime.utcnow()
        due = db.execute(
            "SELECT s.*, p.public_id, p.full_name FROM campaign_steps s "
            "JOIN prospects p ON p.id = s.prospect_id "
            "WHERE s.campaign_id=? AND s.status='pending' AND s.run_after <= ? "
            "ORDER BY s.run_after LIMIT ?",
            (camp["id"], now.isoformat(), max_actions),
        ).fetchall()

        client = LinkedInClient.get()
        attempted = 0
        for step in due:
            try:
                if step["step"] == "connect":
                    body = (camp["connection_template"] or "").replace(
                        "{name}", step["full_name"] or ""
                    )
                    client.add_connection(step["public_id"], message=body)
                else:
                    idx = int(step["step"].split("_")[-1]) - 1
                    tpl = followups[idx]
                    body = tpl["body"].replace("{name}", step["full_name"] or "")
                    client.send_message(message_body=body, recipients=[step["public_id"]])
                db.execute(
                    "UPDATE campaign_steps SET status='sent', sent_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), step["id"]),
                )
                attempted += 1
                # Schedule next step
                nxt_idx = (
                    1
                    if step["step"] == "connect"
                    else int(step["step"].split("_")[-1]) + 1
                )
                if nxt_idx <= len(followups):
                    delay = followups[nxt_idx - 1].get("delay_hours", 48)
                    db.execute(
                        "INSERT OR IGNORE INTO campaign_steps(campaign_id, prospect_id, step, status, run_after) "
                        "VALUES(?,?,?,?,?)",
                        (
                            camp["id"],
                            step["prospect_id"],
                            f"followup_{nxt_idx}",
                            "pending",
                            (now + timedelta(hours=delay)).isoformat(),
                        ),
                    )
            except Exception as e:
                db.execute(
                    "UPDATE campaign_steps SET status='failed', error=? WHERE id=?",
                    (str(e)[:500], step["id"]),
                )
        return {"campaign": name, "attempted": attempted}

    @mcp.tool()
    def list_campaigns() -> list[dict[str, Any]]:
        db = get_db()
        rows = db.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall()
        out = as_list(rows)
        for r in out:
            r["followup_templates"] = jload(r.get("followup_templates"))
        return out
