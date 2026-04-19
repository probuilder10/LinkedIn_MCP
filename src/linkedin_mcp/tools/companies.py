from __future__ import annotations

from typing import Any

from ..client import LinkedInClient


def register(mcp) -> None:
    @mcp.tool()
    def search_companies(keywords: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Search LinkedIn companies by keywords."""
        return LinkedInClient.get().search_companies(keywords=keywords, limit=limit)

    @mcp.tool()
    def get_company(public_id: str) -> dict[str, Any]:
        """Fetch the full company profile by public_id (e.g. "anthropic")."""
        return LinkedInClient.get().get_company(public_id)

    @mcp.tool()
    def search_jobs(keywords: str | None = None, location_name: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
        """Search LinkedIn job listings (handy as a signal source for hiring activity)."""
        return LinkedInClient.get().search_jobs(keywords=keywords, location_name=location_name, limit=limit)
