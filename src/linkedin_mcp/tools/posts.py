from __future__ import annotations

from datetime import datetime
from typing import Any

from ..client import LinkedInClient
from ..config import settings
from ..storage.db import as_dict, as_list, get_db


def register(mcp) -> None:
    @mcp.tool()
    def publish_post(text: str, visibility: str = "ANYONE") -> dict[str, Any]:
        """Publish a LinkedIn post immediately. visibility: ANYONE | CONNECTIONS."""
        return LinkedInClient.get().post_text(text=text, visibility=visibility)

    @mcp.tool()
    def draft_post(
        topic: str,
        tone: str = "direct, no buzzwords",
        max_chars: int = 1300,
        format_style: str = "story",
    ) -> dict[str, Any]:
        """Draft a LinkedIn post from a topic.

        Uses OpenAI when OPENAI_API_KEY is set; otherwise returns a template.
        format_style: story | listicle | hot_take | how_to
        """
        if settings.openai_api_key:
            try:
                from openai import OpenAI  # type: ignore

                prompt = (
                    f"Write a LinkedIn post. Topic: {topic}. Tone: {tone}. Style: {format_style}. "
                    f"Hard cap {max_chars} chars. First line must hook the scroll. "
                    "No emojis, no hashtags at the top, no '#trust me bro'. One CTA line at the end."
                )
                oai = OpenAI(api_key=settings.openai_api_key)
                resp = oai.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.8,
                )
                return {"text": resp.choices[0].message.content, "source": "openai"}
            except Exception as e:
                return {"text": _fallback_post(topic, format_style), "source": f"fallback:{e}"}
        return {"text": _fallback_post(topic, format_style), "source": "fallback"}

    @mcp.tool()
    def react_to_post(post_urn_id: str, reaction: str = "LIKE") -> dict[str, Any]:
        """React to a post. reaction: LIKE | PRAISE | EMPATHY | INTEREST | APPRECIATION | ENTERTAINMENT."""
        allowed = {"LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION", "ENTERTAINMENT"}
        if reaction not in allowed:
            raise ValueError(f"reaction must be one of {sorted(allowed)}")
        LinkedInClient.get().api.react_to_post(post_urn_id, reaction_type=reaction)
        return {"ok": True, "post": post_urn_id, "reaction": reaction}

    @mcp.tool()
    def profile_views() -> dict[str, Any]:
        """Return profile-view stats (how many, who, trend)."""
        return LinkedInClient.get().api.get_current_profile_views()

    @mcp.tool()
    def feed_posts(limit: int = 20) -> list[dict[str, Any]]:
        """Return posts from your feed (for content research / signals)."""
        return LinkedInClient.get().api.get_feed_posts(limit=limit, exclude_promoted_posts=True)

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


def _fallback_post(topic: str, style: str) -> str:
    if style == "listicle":
        return (
            f"5 things I learned about {topic} this week:\n\n"
            "1. <point>\n2. <point>\n3. <point>\n4. <point>\n5. <point>\n\n"
            "What would you add?"
        )
    if style == "hot_take":
        return f"Unpopular take on {topic}: <claim>.\n\nHere's why I think the consensus is wrong: <reason>.\n\nDisagree?"
    if style == "how_to":
        return f"How to ship {topic} in under a week:\n\n- Step 1\n- Step 2\n- Step 3\n\nWhat's your version?"
    return (
        f"Short story about {topic}.\n\n"
        "<set the scene>\n<conflict>\n<resolution>\n\n"
        "Happy to compare notes — what's your take?"
    )
