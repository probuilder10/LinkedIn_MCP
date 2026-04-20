"""Post-level engagement analytics and warm-lead extraction."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ..client import LinkedInClient


def register(mcp) -> None:
    @mcp.tool()
    def my_recent_posts(post_count: int = 10) -> list[dict[str, Any]]:
        """Return the current user's most recent posts with engagement stats."""
        me = LinkedInClient.get().api.get_user_profile()["miniProfile"]
        return LinkedInClient.get().api.get_profile_posts(
            public_id=me["publicIdentifier"], post_count=post_count
        )

    @mcp.tool()
    def post_reactions(post_urn: str, max_results: int = 100) -> list[dict[str, Any]]:
        """List everyone who reacted to a post (warm leads)."""
        return LinkedInClient.get().api.get_post_reactions(post_urn, max_results=max_results) or []

    @mcp.tool()
    def post_comments(post_urn: str, comment_count: int = 100) -> list[dict[str, Any]]:
        """List comments on a post."""
        return LinkedInClient.get().api.get_post_comments(post_urn=post_urn, comment_count=comment_count)

    @mcp.tool()
    def warm_leads_from_post(post_urn: str, max_reactions: int = 100) -> dict[str, Any]:
        """Extract deduplicated public_ids of engagers (reactors + commenters) on one post.

        Returns counts + a flat `engagers` list ready to feed into `score_prospect`.
        """
        client = LinkedInClient.get()
        reactions = client.api.get_post_reactions(post_urn, max_results=max_reactions) or []
        comments = client.api.get_post_comments(post_urn=post_urn, comment_count=max_reactions)
        engagers: dict[str, dict[str, Any]] = {}
        for r in reactions:
            pid = _public_id(r.get("reactorLockup") or r)
            if pid:
                engagers.setdefault(pid, {"public_id": pid, "name": _display_name(r.get("reactorLockup") or r), "via": []})
                engagers[pid]["via"].append(f"reaction:{r.get('reactionType','LIKE')}")
        for c in comments:
            pid = _public_id(c.get("commenter") or c)
            if pid:
                engagers.setdefault(pid, {"public_id": pid, "name": _display_name(c.get("commenter") or c), "via": []})
                engagers[pid]["via"].append("comment")
        return {
            "post_urn": post_urn,
            "n_reactions": len(reactions),
            "n_comments": len(comments),
            "n_engagers": len(engagers),
            "engagers": list(engagers.values()),
        }

    @mcp.tool()
    def content_performance(post_count: int = 20) -> dict[str, Any]:
        """Summarize my recent posts: which topics and formats get the most engagement.

        Returns top-N topics (naive keyword buckets) and engagement stats, plus
        per-post breakdown so Claude can reason about what to write next.
        """
        me = LinkedInClient.get().api.get_user_profile()["miniProfile"]
        posts = LinkedInClient.get().api.get_profile_posts(public_id=me["publicIdentifier"], post_count=post_count)
        if not posts:
            return {"posts": [], "avg_reactions": 0, "avg_comments": 0, "top_words": []}
        reactions_total = sum(int(p.get("numReactions") or 0) for p in posts)
        comments_total = sum(int(p.get("numComments") or 0) for p in posts)
        avg_r = reactions_total / len(posts)
        avg_c = comments_total / len(posts)

        # naive word frequency across commentary, weighted by engagement
        weighted: Counter[str] = Counter()
        for p in posts:
            text = (p.get("commentary") or p.get("text") or "").lower()
            score = int(p.get("numReactions") or 0) + 3 * int(p.get("numComments") or 0)
            for w in text.split():
                w = _clean(w)
                if len(w) < 4 or w in _STOPWORDS:
                    continue
                weighted[w] += score + 1
        top = weighted.most_common(15)

        return {
            "total_posts": len(posts),
            "avg_reactions": round(avg_r, 1),
            "avg_comments": round(avg_c, 1),
            "top_words": [{"word": w, "weighted": c} for w, c in top],
            "posts": [
                {
                    "urn": p.get("urn"),
                    "reactions": p.get("numReactions"),
                    "comments": p.get("numComments"),
                    "preview": (p.get("commentary") or p.get("text") or "")[:140],
                }
                for p in posts
            ],
        }


_STOPWORDS = {
    "about", "after", "again", "also", "been", "before", "being", "here", "just",
    "like", "more", "most", "over", "some", "than", "that", "them", "then", "these",
    "they", "this", "those", "were", "what", "when", "which", "with", "would", "your",
    "from", "have", "into", "only", "their", "there", "very", "will", "https",
}


def _clean(w: str) -> str:
    return "".join(c for c in w if c.isalnum())


def _public_id(obj: dict | None) -> str | None:
    if not obj:
        return None
    return obj.get("publicIdentifier") or obj.get("public_id")


def _display_name(obj: dict | None) -> str:
    if not obj:
        return ""
    return obj.get("name") or f"{obj.get('firstName','')} {obj.get('lastName','')}".strip()
