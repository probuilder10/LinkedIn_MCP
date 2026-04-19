from __future__ import annotations

from datetime import datetime
from typing import Any

from ..client import LinkedInClient
from ..storage.db import as_dict, as_list, get_db


def register(mcp) -> None:
    @mcp.tool()
    def publish_post(text: str, visibility: str = "ANYONE") -> dict[str, Any]:
        """Publish a LinkedIn post immediately. visibility: ANYONE | CONNECTIONS."""
        return LinkedInClient.get().post_text(text=text, visibility=visibility)

    @mcp.tool()
    def schedule_post(text: str, run_at_iso: str, visibility: str = "ANYONE") -> dict[str, Any]:
        """Schedule a post for later. run_at_iso must be ISO-8601 (e.g. 2026-04-20T09:00:00+00:00)."""
        try:
            run_at = datetime.fromisoformat(run_at_iso)
        except ValueError as e:
            raise ValueError(f"run_at_iso must be ISO-8601: {e}") from e
        db = get_db()
        cur = db.execute(
            "INSERT INTO scheduled_posts(text, visibility, run_at) VALUES(?,?,?)",
            (text, visibility, run_at.isoformat()),
        )
        return {"id": cur.lastrowid, "run_at": run_at.isoformat(), "status": "scheduled"}

    @mcp.tool()
    def list_scheduled_posts(status: str | None = None) -> list[dict[str, Any]]:
        """List scheduled posts, optionally filtered by status (scheduled|published|failed)."""
        db = get_db()
        if status:
            rows = db.execute(
                "SELECT * FROM scheduled_posts WHERE status=? ORDER BY run_at", (status,)
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM scheduled_posts ORDER BY run_at").fetchall()
        return as_list(rows)

    @mcp.tool()
    def cancel_scheduled_post(post_id: int) -> dict[str, Any]:
        """Cancel a scheduled post that hasn't run yet."""
        db = get_db()
        row = db.execute("SELECT * FROM scheduled_posts WHERE id=?", (post_id,)).fetchone()
        if not row:
            raise ValueError(f"post {post_id} not found")
        if row["status"] != "scheduled":
            raise ValueError(f"cannot cancel post in status {row['status']}")
        db.execute("UPDATE scheduled_posts SET status='cancelled' WHERE id=?", (post_id,))
        return as_dict(db.execute("SELECT * FROM scheduled_posts WHERE id=?", (post_id,)).fetchone())
