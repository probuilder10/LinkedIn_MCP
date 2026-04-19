"""Thin wrapper around linkedin-api (Voyager) with rate limiting + jitter."""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass
from datetime import date
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .config import settings
from .storage.db import get_db

logger = logging.getLogger(__name__)


class LinkedInAuthError(RuntimeError):
    pass


class LinkedInRateLimitError(RuntimeError):
    pass


@dataclass
class Quota:
    connection_requests: int
    messages: int
    profile_views: int


class LinkedInClient:
    """Singleton wrapper. Not thread-safe for underlying session; we use a lock."""

    _instance: "LinkedInClient | None" = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        from linkedin_api import Linkedin  # imported lazily for test envs

        self._Linkedin = Linkedin
        self._api: Any | None = None
        self._api_lock = threading.Lock()

    @classmethod
    def get(cls) -> "LinkedInClient":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _build(self) -> Any:
        if settings.linkedin_li_at:
            cookies = {"li_at": settings.linkedin_li_at}
            if settings.linkedin_jsessionid:
                cookies["JSESSIONID"] = settings.linkedin_jsessionid.strip('"')
            # linkedin-api accepts a `cookies` dict via the RequestsCookieJar; we feed it directly.
            try:
                return self._Linkedin(
                    username=settings.linkedin_email or "cookie@local",
                    password=settings.linkedin_password or "cookie",
                    cookies=cookies,
                    authenticate=False,
                )
            except Exception as e:  # pragma: no cover
                raise LinkedInAuthError(f"cookie auth failed: {e}") from e
        if settings.linkedin_email and settings.linkedin_password:
            try:
                return self._Linkedin(settings.linkedin_email, settings.linkedin_password)
            except Exception as e:
                raise LinkedInAuthError(f"password auth failed: {e}") from e
        raise LinkedInAuthError(
            "No LinkedIn credentials configured. Set LINKEDIN_LI_AT (recommended) in .env"
        )

    @property
    def api(self) -> Any:
        if self._api is None:
            with self._api_lock:
                if self._api is None:
                    self._api = self._build()
        return self._api

    # ---------- Rate limiting ----------

    def _today(self) -> str:
        return date.today().isoformat()

    def _quota_today(self) -> Quota:
        db = get_db()
        row = db.execute(
            "SELECT connection_requests, messages, profile_views FROM quota WHERE day=?",
            (self._today(),),
        ).fetchone()
        if not row:
            return Quota(0, 0, 0)
        return Quota(*row)

    def _bump(self, field: str) -> None:
        db = get_db()
        with db:
            db.execute(
                "INSERT INTO quota(day, connection_requests, messages, profile_views) "
                "VALUES(?,0,0,0) ON CONFLICT(day) DO NOTHING",
                (self._today(),),
            )
            db.execute(f"UPDATE quota SET {field}={field}+1 WHERE day=?", (self._today(),))

    def _check_quota(self, action: str) -> None:
        q = self._quota_today()
        limits = {
            "connection_requests": settings.max_connection_requests_per_day,
            "messages": settings.max_messages_per_day,
            "profile_views": settings.max_profile_views_per_day,
        }
        current = getattr(q, action)
        if current >= limits[action]:
            raise LinkedInRateLimitError(
                f"Daily {action} quota reached ({current}/{limits[action]}). "
                f"Adjust limits in .env or wait 24h."
            )

    def _jitter(self) -> None:
        time.sleep(random.uniform(settings.min_action_delay_seconds, settings.max_action_delay_seconds))

    # ---------- Tool methods (thin passthroughs with retries) ----------

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=20),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    def search_people(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.api.search_people(**kwargs)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=20),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    )
    def get_profile(self, public_id: str | None = None, urn_id: str | None = None) -> dict[str, Any]:
        self._check_quota("profile_views")
        profile = self.api.get_profile(public_id=public_id, urn_id=urn_id)
        self._bump("profile_views")
        return profile

    def get_profile_contact_info(self, public_id: str | None = None, urn_id: str | None = None) -> dict[str, Any]:
        return self.api.get_profile_contact_info(public_id=public_id, urn_id=urn_id)

    def search_companies(self, keywords: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        return self.api.search_companies(keywords=keywords, limit=limit)

    def get_company(self, public_id: str) -> dict[str, Any]:
        return self.api.get_company(public_id)

    def get_connections(self) -> list[dict[str, Any]]:
        return self.api.get_profile_connections(self.api.get_user_profile()["miniProfile"]["entityUrn"].split(":")[-1])

    def add_connection(self, profile_public_id: str, message: str = "") -> dict[str, Any]:
        self._check_quota("connection_requests")
        self._jitter()
        res = self.api.add_connection(profile_public_id=profile_public_id, message=message)
        self._bump("connection_requests")
        return {"ok": not res, "public_id": profile_public_id}  # lib returns False on success

    def send_message(self, message_body: str, conversation_urn_id: str | None = None, recipients: list[str] | None = None) -> dict[str, Any]:
        self._check_quota("messages")
        self._jitter()
        res = self.api.send_message(
            message_body=message_body,
            conversation_urn_id=conversation_urn_id,
            recipients=recipients,
        )
        self._bump("messages")
        return {"ok": not res}

    def list_conversations(self) -> list[dict[str, Any]]:
        return self.api.get_conversations()

    def get_conversation(self, conversation_urn_id: str) -> dict[str, Any]:
        return self.api.get_conversation(conversation_urn_id)

    def post_text(self, text: str, visibility: str = "ANYONE") -> dict[str, Any]:
        # linkedin-api lacks a native post helper; use the internal /voyager/api/contentcreation endpoint via `_fetch`.
        payload = {
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        res = self.api._fetch(  # type: ignore[attr-defined]
            "/posts",
            method="POST",
            base_request=True,
            data=payload,
        )
        return {"status": getattr(res, "status_code", None), "body": getattr(res, "text", "")[:500]}

    def search_jobs(self, keywords: str | None = None, location_name: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
        return self.api.search_jobs(keywords=keywords, location_name=location_name, limit=limit)
