"""Best-effort outbound webhook notifier (Slack / Discord / custom)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import settings

logger = logging.getLogger(__name__)


def notify(event: str, payload: dict[str, Any]) -> bool:
    """POST `{event, payload, text}` to NOTIFY_WEBHOOK_URL. Never raises."""
    url = settings.notify_webhook_url
    if not url:
        return False
    text = f"[{event}] {_summary(payload)}"
    body = {"event": event, "payload": payload, "text": text}
    try:
        httpx.post(url, json=body, timeout=5.0)
        return True
    except Exception as e:  # pragma: no cover
        logger.warning("notify failed: %s", e)
        return False


def _summary(payload: dict[str, Any]) -> str:
    if "name" in payload and "to" in payload:
        to = payload["to"] or {}
        return f"{payload['name']} -> {to.get('title','?')} at {to.get('company','?')}"
    if "campaign" in payload:
        return f"campaign={payload['campaign']} attempted={payload.get('attempted')}"
    return str(payload)[:200]
