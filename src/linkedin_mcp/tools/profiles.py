from __future__ import annotations

from typing import Any

from ..client import LinkedInClient


def register(mcp) -> None:
    @mcp.tool()
    def search_people(
        keywords: str | None = None,
        current_company: list[str] | None = None,
        past_companies: list[str] | None = None,
        industries: list[str] | None = None,
        school: str | None = None,
        network_depths: list[str] | None = None,
        title: str | None = None,
        regions: list[str] | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        """Search LinkedIn people by natural-language keywords plus structured filters.

        network_depths: e.g. ["F","S","O"] for first/second/out-of-network.
        regions: LinkedIn geo URN ids as strings.
        Returns lightweight hits with public_id/urn_id/full_name/headline.
        """
        kwargs = {
            "keywords": keywords,
            "current_company": current_company,
            "past_companies": past_companies,
            "industries": industries,
            "schools": [school] if school else None,
            "network_depths": network_depths,
            "title": title,
            "regions": regions,
            "limit": limit,
        }
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        return LinkedInClient.get().search_people(**kwargs)

    @mcp.tool()
    def get_profile(public_id: str | None = None, urn_id: str | None = None) -> dict[str, Any]:
        """Fetch the full profile document (experience, education, skills, etc.)."""
        if not (public_id or urn_id):
            raise ValueError("provide public_id or urn_id")
        return LinkedInClient.get().get_profile(public_id=public_id, urn_id=urn_id)

    @mcp.tool()
    def get_profile_contact_info(
        public_id: str | None = None, urn_id: str | None = None
    ) -> dict[str, Any]:
        """Fetch the contact-info panel (email/phone/sites) if visible to the current user."""
        return LinkedInClient.get().get_profile_contact_info(public_id=public_id, urn_id=urn_id)
