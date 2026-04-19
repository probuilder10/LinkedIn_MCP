from __future__ import annotations

from typing import Any

from ..config import settings
from ..storage.db import get_db


def register(mcp) -> None:
    @mcp.tool()
    def whoami() -> dict[str, Any]:
        """Confirm auth is working and return the current LinkedIn profile."""
        from ..client import LinkedInClient

        me = LinkedInClient.get().api.get_user_profile()
        mini = me.get("miniProfile", {})
        return {
            "ok": True,
            "public_id": mini.get("publicIdentifier"),
            "name": f"{mini.get('firstName','')} {mini.get('lastName','')}".strip(),
            "headline": mini.get("occupation"),
        }

    @mcp.tool()
    def quota_status() -> dict[str, Any]:
        """Return today's action counts vs daily caps."""
        db = get_db()
        from datetime import date

        row = db.execute(
            "SELECT connection_requests, messages, profile_views FROM quota WHERE day=?",
            (date.today().isoformat(),),
        ).fetchone()
        current = (
            {"connection_requests": 0, "messages": 0, "profile_views": 0}
            if not row
            else dict(row)
        )
        return {
            "today": current,
            "limits": {
                "connection_requests": settings.max_connection_requests_per_day,
                "messages": settings.max_messages_per_day,
                "profile_views": settings.max_profile_views_per_day,
            },
        }
