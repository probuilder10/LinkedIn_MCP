"""Admin CLI for ops tasks that don't go through an MCP client.

Usage:
    linkedin-mcp-admin campaigns list
    linkedin-mcp-admin campaigns tick <name>
    linkedin-mcp-admin prospects list [--icp NAME] [--min-score N]
    linkedin-mcp-admin posts list [--status STATUS]
    linkedin-mcp-admin quota
    linkedin-mcp-admin db backup <path>
    linkedin-mcp-admin db reset
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from .config import settings


def _pretty(obj) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="linkedin-mcp-admin")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("campaigns")
    csub = c.add_subparsers(dest="subcmd", required=True)
    csub.add_parser("list")
    ct = csub.add_parser("tick")
    ct.add_argument("name")
    ct.add_argument("--max", type=int, default=20)

    pr = sub.add_parser("prospects")
    prsub = pr.add_subparsers(dest="subcmd", required=True)
    prl = prsub.add_parser("list")
    prl.add_argument("--icp")
    prl.add_argument("--min-score", type=float, default=0.0)
    prl.add_argument("--status")
    prl.add_argument("--limit", type=int, default=50)

    ps = sub.add_parser("posts")
    pssub = ps.add_subparsers(dest="subcmd", required=True)
    psl = pssub.add_parser("list")
    psl.add_argument("--status")

    sub.add_parser("quota")

    db = sub.add_parser("db")
    dbsub = db.add_subparsers(dest="subcmd", required=True)
    dbb = dbsub.add_parser("backup")
    dbb.add_argument("dest")
    dbsub.add_parser("reset")

    args = p.parse_args(argv)

    if args.cmd == "campaigns":
        return _campaigns(args)
    if args.cmd == "prospects":
        return _prospects(args)
    if args.cmd == "posts":
        return _posts(args)
    if args.cmd == "quota":
        return _quota()
    if args.cmd == "db":
        return _db(args)
    return 2


def _campaigns(args) -> int:
    from .storage.db import as_list, get_db, jload

    db = get_db()
    if args.subcmd == "list":
        rows = as_list(db.execute("SELECT * FROM campaigns ORDER BY id DESC").fetchall())
        for r in rows:
            r["followup_templates"] = jload(r.get("followup_templates"))
        _pretty(rows)
        return 0
    if args.subcmd == "tick":
        from .tools import campaigns as cmod

        class _R:
            def tool(self, *a, **k):
                def d(f):
                    setattr(self, f.__name__, f)
                    return f

                return d

            def prompt(self, *a, **k):
                def d(f):
                    return f

                return d

        r = _R()
        cmod.register(r)
        _pretty(r.run_campaign_tick(args.name, max_actions=args.max))  # type: ignore[attr-defined]
        return 0
    return 2


def _prospects(args) -> int:
    from .storage.db import as_list, get_db

    db = get_db()
    q = "SELECT p.public_id, p.full_name, p.headline, p.score, p.status FROM prospects p LEFT JOIN icp i ON i.id=p.icp_id WHERE p.score >= ?"
    params: list = [args.min_score]
    if args.icp:
        q += " AND i.name=?"
        params.append(args.icp)
    if args.status:
        q += " AND p.status=?"
        params.append(args.status)
    q += " ORDER BY p.score DESC LIMIT ?"
    params.append(args.limit)
    _pretty(as_list(db.execute(q, params).fetchall()))
    return 0


def _posts(args) -> int:
    from .storage.db import as_list, get_db

    db = get_db()
    if args.status:
        rows = db.execute("SELECT * FROM scheduled_posts WHERE status=? ORDER BY run_at", (args.status,)).fetchall()
    else:
        rows = db.execute("SELECT * FROM scheduled_posts ORDER BY run_at").fetchall()
    _pretty(as_list(rows))
    return 0


def _quota() -> int:
    from datetime import date

    from .storage.db import get_db

    db = get_db()
    row = db.execute(
        "SELECT connection_requests, messages, profile_views FROM quota WHERE day=?",
        (date.today().isoformat(),),
    ).fetchone()
    today = {"connection_requests": 0, "messages": 0, "profile_views": 0} if not row else dict(row)
    _pretty(
        {
            "today": today,
            "limits": {
                "connection_requests": settings.max_connection_requests_per_day,
                "messages": settings.max_messages_per_day,
                "profile_views": settings.max_profile_views_per_day,
            },
        }
    )
    return 0


def _db(args) -> int:
    path = Path(settings.linkedin_mcp_db)
    if args.subcmd == "backup":
        if not path.exists():
            print(f"db not found at {path}", file=sys.stderr)
            return 1
        dest = Path(args.dest)
        if dest.is_dir():
            dest = dest / f"linkedin_mcp.{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.sqlite"
        shutil.copy2(path, dest)
        print(f"backed up -> {dest}")
        return 0
    if args.subcmd == "reset":
        if path.exists():
            path.unlink()
            print(f"deleted {path}")
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
