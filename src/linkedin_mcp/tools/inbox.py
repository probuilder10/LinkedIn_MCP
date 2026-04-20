"""Inbox triage: list unread, classify, draft AI replies, bulk-reply."""

from __future__ import annotations

from typing import Any

from ..client import LinkedInClient
from ..config import settings


def register(mcp) -> None:
    @mcp.tool()
    def list_unread(limit: int = 30) -> list[dict[str, Any]]:
        """Return unread conversations with a short preview of the latest message."""
        convs = LinkedInClient.get().api.get_conversations() or []
        out: list[dict[str, Any]] = []
        for c in convs:
            if _is_read(c):
                continue
            out.append(_preview(c))
            if len(out) >= limit:
                break
        return out

    @mcp.tool()
    def triage_inbox(limit: int = 20) -> dict[str, Any]:
        """Classify unread conversations into buckets: reply, schedule_call, ignore, spam.

        Uses OpenAI if configured; otherwise keyword heuristics.
        """
        convs = LinkedInClient.get().api.get_conversations() or []
        unread = [c for c in convs if not _is_read(c)][:limit]
        buckets: dict[str, list[dict[str, Any]]] = {
            "reply": [],
            "schedule_call": [],
            "ignore": [],
            "spam": [],
        }
        for c in unread:
            preview = _preview(c)
            label = _classify(preview["latest_text"])
            preview["label"] = label
            buckets[label].append(preview)
        return {
            "total_unread": len(unread),
            "counts": {k: len(v) for k, v in buckets.items()},
            "buckets": buckets,
        }

    @mcp.tool()
    def draft_reply(conversation_urn_id: str, goal: str = "acknowledge and move the conversation forward") -> dict[str, Any]:
        """Draft a reply for a specific conversation using the last ~10 messages as context."""
        client = LinkedInClient.get()
        conv = client.api.get_conversation(conversation_urn_id)
        thread = _messages(conv)[-10:]
        context = "\n".join(f"{m['from']}: {m['text']}" for m in thread)

        if settings.openai_api_key:
            try:
                from openai import OpenAI  # type: ignore

                prompt = (
                    f"You are replying on LinkedIn as the account owner. Goal: {goal}.\n"
                    f"Keep it short (<= 400 chars), no emojis, plain tone.\n"
                    f"Conversation so far:\n{context}\n\n"
                    "Write ONLY the reply, no preamble."
                )
                oai = OpenAI(api_key=settings.openai_api_key)
                resp = oai.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.5,
                )
                return {"body": resp.choices[0].message.content, "source": "openai"}
            except Exception as e:
                return {"body": _fallback_reply(thread, goal), "source": f"fallback:{e}"}
        return {"body": _fallback_reply(thread, goal), "source": "fallback"}

    @mcp.tool()
    def bulk_reply(
        drafts: list[dict[str, str]], dry_run: bool = True
    ) -> dict[str, Any]:
        """Send a list of pre-drafted replies.

        drafts: [{"conversation_urn_id": "...", "body": "..."}, ...]
        Set dry_run=False to actually send. Respects the daily messages quota.
        """
        client = LinkedInClient.get()
        results: list[dict[str, Any]] = []
        for d in drafts:
            if not d.get("conversation_urn_id") or not d.get("body"):
                results.append({"skip": True, "reason": "missing_fields"})
                continue
            if dry_run:
                results.append({"ok": True, "dry_run": True, **d})
                continue
            try:
                r = client.send_message(
                    message_body=d["body"],
                    conversation_urn_id=d["conversation_urn_id"],
                )
                results.append({"ok": r["ok"], "conversation_urn_id": d["conversation_urn_id"]})
            except Exception as e:
                results.append({"ok": False, "error": str(e)})
        return {"sent": sum(1 for r in results if r.get("ok") and not r.get("dry_run")), "results": results}


# ---------- helpers ----------

_SPAM_HINTS = ("check my page", "buy now", "investment opportunity", "crypto", "click here", "free trial")
_CALL_HINTS = ("call", "15 min", "15-min", "chat", "demo", "zoom", "google meet", "calendly", "schedule")


def _is_read(conv: dict) -> bool:
    return bool(conv.get("read")) or bool(conv.get("unreadCount") == 0)


def _messages(conv: dict) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    for el in conv.get("elements") or conv.get("events") or conv.get("messages") or []:
        event = el.get("eventContent") or el.get("value") or el
        body = (
            event.get("com.linkedin.voyager.messaging.event.MessageEvent", {}).get("attributedBody", {}).get("text")
            or event.get("attributedBody", {}).get("text")
            or event.get("body")
            or el.get("text")
            or ""
        )
        sender = (
            el.get("from", {}).get("com.linkedin.voyager.messaging.MessagingMember", {}).get("miniProfile", {}).get("publicIdentifier")
            or el.get("from", {}).get("publicIdentifier")
            or "them"
        )
        msgs.append({"from": sender, "text": body})
    return msgs


def _preview(conv: dict) -> dict[str, Any]:
    msgs = _messages(conv)
    latest = msgs[-1] if msgs else {"from": "?", "text": ""}
    return {
        "conversation_urn_id": conv.get("entityUrn", "").split(":")[-1],
        "participants": conv.get("participants") or [],
        "latest_from": latest["from"],
        "latest_text": latest["text"],
    }


def _classify(text: str) -> str:
    t = (text or "").lower()
    if any(h in t for h in _SPAM_HINTS):
        return "spam"
    if any(h in t for h in _CALL_HINTS):
        return "schedule_call"
    if len(t) < 5:
        return "ignore"
    return "reply"


def _fallback_reply(thread: list[dict], goal: str) -> str:
    last_them = next((m["text"] for m in reversed(thread) if m["from"] != "me"), "")
    snippet = (last_them[:80] + "…") if len(last_them) > 80 else last_them
    return f"Thanks for the note re: '{snippet}'. Short reply: {goal}. Up for a quick next step?"
