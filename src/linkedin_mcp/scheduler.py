"""Background scheduler for scheduled posts and campaign ticks."""

from __future__ import annotations

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

from .storage.db import get_db

logger = logging.getLogger(__name__)


def _publish_due_posts() -> None:
    from .client import LinkedInClient

    db = get_db()
    now = datetime.utcnow().isoformat()
    rows = db.execute(
        "SELECT * FROM scheduled_posts WHERE status='scheduled' AND run_at<=?", (now,)
    ).fetchall()
    for r in rows:
        try:
            LinkedInClient.get().post_text(r["text"], visibility=r["visibility"])
            db.execute(
                "UPDATE scheduled_posts SET status='published', published_at=? WHERE id=?",
                (datetime.utcnow().isoformat(), r["id"]),
            )
            logger.info("published scheduled post %s", r["id"])
        except Exception as e:  # pragma: no cover
            db.execute(
                "UPDATE scheduled_posts SET status='failed', error=? WHERE id=?",
                (str(e)[:500], r["id"]),
            )
            logger.exception("scheduled post %s failed", r["id"])


def _tick_active_campaigns() -> None:
    from .tools.campaigns import register as _  # noqa

    db = get_db()
    names = [
        r["name"] for r in db.execute("SELECT name FROM campaigns WHERE status='active'").fetchall()
    ]
    if not names:
        return
    # Inline tick logic to avoid MCP decorator indirection.
    from .client import LinkedInClient
    from datetime import timedelta
    from .storage.db import jload

    client = LinkedInClient.get()
    for name in names:
        camp = db.execute("SELECT * FROM campaigns WHERE name=?", (name,)).fetchone()
        followups = jload(camp["followup_templates"]) or []
        now = datetime.utcnow()
        due = db.execute(
            "SELECT s.*, p.public_id, p.full_name FROM campaign_steps s "
            "JOIN prospects p ON p.id = s.prospect_id "
            "WHERE s.campaign_id=? AND s.status='pending' AND s.run_after <= ? "
            "ORDER BY s.run_after LIMIT 10",
            (camp["id"], now.isoformat()),
        ).fetchall()
        for step in due:
            try:
                if step["step"] == "connect":
                    body = (camp["connection_template"] or "").replace("{name}", step["full_name"] or "")
                    client.add_connection(step["public_id"], message=body)
                else:
                    idx = int(step["step"].split("_")[-1]) - 1
                    tpl = followups[idx]
                    body = tpl["body"].replace("{name}", step["full_name"] or "")
                    urn_id = client._resolve_urn_id(step["public_id"])
                    client.send_message(message_body=body, recipient_urn_ids=[urn_id])
                db.execute(
                    "UPDATE campaign_steps SET status='sent', sent_at=? WHERE id=?",
                    (datetime.utcnow().isoformat(), step["id"]),
                )
                nxt_idx = 1 if step["step"] == "connect" else int(step["step"].split("_")[-1]) + 1
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


_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    s = BackgroundScheduler(daemon=True)
    s.add_job(_publish_due_posts, "interval", minutes=1, id="posts")
    s.add_job(_tick_active_campaigns, "interval", minutes=5, id="campaigns")
    s.start()
    _scheduler = s
    logger.info("scheduler started")
    return s
