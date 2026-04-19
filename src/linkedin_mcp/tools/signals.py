"""Intent-signal detection: job changes, fundraising mentions, hiring spikes, engagement."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..client import LinkedInClient
from ..storage.db import as_list, get_db, jdump, jload


def register(mcp) -> None:
    @mcp.tool()
    def detect_job_changes(lookback_days: int = 30) -> list[dict[str, Any]]:
        """Scan stored prospects and surface people whose current company changed
        vs the raw profile we saw last time. Returns the diff list."""
        db = get_db()
        rows = db.execute(
            "SELECT id, public_id, full_name, company, title, raw FROM prospects "
            "WHERE public_id IS NOT NULL"
        ).fetchall()
        changes: list[dict[str, Any]] = []
        client = LinkedInClient.get()
        since = datetime.utcnow() - timedelta(days=lookback_days)
        for r in rows:
            try:
                fresh = client.get_profile(public_id=r["public_id"])
            except Exception:
                continue
            exp = fresh.get("experience") or []
            if not exp:
                continue
            latest = exp[0]
            new_company = latest.get("companyName")
            new_title = latest.get("title")
            start = latest.get("timePeriod", {}).get("startDate", {})
            started = datetime(start.get("year", 1900), start.get("month", 1), 1)
            if started < since:
                continue
            if (new_company and new_company != r["company"]) or (
                new_title and new_title != r["title"]
            ):
                changes.append(
                    {
                        "prospect_id": r["id"],
                        "public_id": r["public_id"],
                        "name": r["full_name"],
                        "from": {"company": r["company"], "title": r["title"]},
                        "to": {"company": new_company, "title": new_title},
                        "started_at": started.isoformat(),
                    }
                )
                db.execute(
                    "INSERT INTO signals(prospect_id, kind, payload) VALUES(?,?,?)",
                    (r["id"], "job_change", jdump(changes[-1])),
                )
                db.execute(
                    "UPDATE prospects SET company=?, title=?, raw=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (new_company, new_title, jdump(fresh), r["id"]),
                )
        return changes

    @mcp.tool()
    def detect_hiring_signal(company_public_id: str, keywords: str | None = None) -> dict[str, Any]:
        """Check if a company is aggressively hiring for a given role."""
        jobs = LinkedInClient.get().search_jobs(
            keywords=keywords, location_name=None, limit=50
        )
        matches = [j for j in jobs if company_public_id.lower() in (j.get("companyName", "").lower())]
        return {"company": company_public_id, "open_roles": len(matches), "jobs": matches[:10]}

    @mcp.tool()
    def list_signals(kind: str | None = None, unprocessed_only: bool = True) -> list[dict[str, Any]]:
        """Read stored intent signals."""
        db = get_db()
        q = "SELECT * FROM signals WHERE 1=1"
        params: list[Any] = []
        if kind:
            q += " AND kind=?"
            params.append(kind)
        if unprocessed_only:
            q += " AND processed=0"
        q += " ORDER BY detected_at DESC LIMIT 500"
        rows = db.execute(q, params).fetchall()
        out = as_list(rows)
        for r in out:
            r["payload"] = jload(r.get("payload"))
        return out

    @mcp.tool()
    def mark_signal_processed(signal_id: int) -> dict[str, Any]:
        db = get_db()
        db.execute("UPDATE signals SET processed=1 WHERE id=?", (signal_id,))
        return {"id": signal_id, "processed": True}
