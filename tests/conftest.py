"""Shared fixtures. We run every test against a throwaway SQLite file and a
fake LinkedIn client so no real network calls ever happen."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.sqlite"
    from linkedin_mcp import config

    # Mutate the live settings object in place so any `from .config import settings`
    # reference stays pointing at the one we're editing.
    config.settings.linkedin_mcp_db = db_path
    config.settings.min_action_delay_seconds = 0
    config.settings.max_action_delay_seconds = 0
    config.settings.max_connection_requests_per_day = 80
    config.settings.max_messages_per_day = 120
    config.settings.max_profile_views_per_day = 200
    config.settings.ensure_paths()
    # Reset per-thread DB connection so next get_db() opens the new file.
    from linkedin_mcp.storage import db as dbmod

    if hasattr(dbmod._LOCAL, "conn"):
        try:
            dbmod._LOCAL.conn.close()
        except Exception:
            pass
        del dbmod._LOCAL.conn
    yield


class FakeLinkedin:
    """Stand-in for linkedin_api.Linkedin — records calls and returns canned data."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []
        self.user = {
            "miniProfile": {
                "entityUrn": "urn:li:fs_miniProfile:me123",
                "publicIdentifier": "me",
                "firstName": "Me",
                "lastName": "Myself",
                "occupation": "Builder",
            }
        }

    def _rec(self, name, **kw):
        self.calls.append((name, kw))

    def get_user_profile(self):
        self._rec("get_user_profile")
        return self.user

    def search_people(self, **kw):
        self._rec("search_people", **kw)
        return [
            {
                "public_id": "jane-doe",
                "urn_id": "jane123",
                "distance": "DISTANCE_2",
                "name": "Jane Doe",
                "jobtitle": "VP Sales at Acme",
            }
        ]

    def get_profile(self, public_id=None, urn_id=None):
        self._rec("get_profile", public_id=public_id, urn_id=urn_id)
        return {
            "entityUrn": f"urn:li:fs_miniProfile:{public_id or urn_id or 'x'}",
            "firstName": "Jane",
            "lastName": "Doe",
            "headline": "VP Sales at Acme, helping SaaS founders scale",
            "summary": "Passionate about B2B SaaS and product-led growth",
            "locationName": "San Francisco, United States",
            "industryName": "Software Development",
            "experience": [
                {
                    "title": "VP Sales",
                    "companyName": "Acme",
                    "timePeriod": {"startDate": {"year": 2026, "month": 3}},
                }
            ],
            "skills": ["SaaS", "B2B", "sales"],
        }

    def get_profile_contact_info(self, public_id=None, urn_id=None):
        return {"emailAddress": "jane@acme.com", "websites": []}

    def search_companies(self, keywords=None, limit=10):
        self._rec("search_companies", keywords=keywords, limit=limit)
        return [{"public_id": "acme", "name": "Acme", "industry": "Software Development", "staffCountRange": "C"}]

    def get_company(self, public_id):
        self._rec("get_company", public_id=public_id)
        return {"public_id": public_id, "name": public_id.title(), "staffCount": 120}

    def search_jobs(self, **kw):
        return [{"companyName": "Acme", "title": "AE"}]

    def get_profile_connections(self, urn_id, **kw):
        self._rec("get_profile_connections", urn_id=urn_id)
        return [{"public_id": "jane-doe"}]

    def add_connection(self, profile_public_id, message="", profile_urn=None):
        self._rec("add_connection", profile_public_id=profile_public_id, message=message)
        return False  # False = success per linkedin-api

    def send_message(self, message_body, conversation_urn_id=None, recipients=None):
        self._rec("send_message", message_body=message_body, conversation_urn_id=conversation_urn_id, recipients=recipients)
        return False

    def get_conversations(self):
        return [{"entityUrn": "urn:li:fs_conversation:c1"}]

    def get_conversation(self, conversation_urn_id):
        return {"urn": conversation_urn_id, "messages": []}

    def _post(self, uri, **kw):
        self._rec("_post", uri=uri)
        return MagicMock(status_code=201, text="{}")


@pytest.fixture
def fake_li(monkeypatch):
    fake = FakeLinkedin()
    from linkedin_mcp import client as cmod

    cmod.LinkedInClient._instance = None  # reset singleton
    monkeypatch.setattr(cmod.LinkedInClient, "_build", lambda self: fake)
    return fake


@pytest.fixture
def mcp_server(fake_li):
    from linkedin_mcp.server import build_server

    os.environ["LINKEDIN_MCP_NO_SCHEDULER"] = "1"
    return build_server()


class ToolRecorder:
    """MCP stub that captures the raw functions so tests can call them directly."""

    def __init__(self):
        self.tools: dict[str, callable] = {}
        self.prompts: dict[str, callable] = {}

    def tool(self, *a, **kw):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn

        return deco

    def prompt(self, *a, **kw):
        def deco(fn):
            self.prompts[fn.__name__] = fn
            return fn

        return deco

    def __getitem__(self, name):
        return self.tools[name]


@pytest.fixture
def tools(fake_li):
    """Load every tool into a dict keyed by name."""
    from linkedin_mcp.tools import register_all

    rec = ToolRecorder()
    register_all(rec)
    return rec

