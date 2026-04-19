"""Sales Navigator-style search built on top of people search + filters.

linkedin-api exposes Voyager's public search which covers most Sales Nav filters
(title/company/industry/geo/seniority). For real Sales Nav-only filters
(decisionmaker, intent, groups, TeamLink), a paid Sales Nav seat is required; we
expose a natural-language wrapper that maps intent -> Voyager filters.
"""

from __future__ import annotations

from typing import Any

from ..client import LinkedInClient

SENIORITY_KEYWORDS = {
    "founder": ["Founder", "Co-Founder", "CEO"],
    "c-level": ["CEO", "CTO", "CFO", "CMO", "COO", "CPO", "Chief"],
    "vp": ["VP", "Vice President"],
    "director": ["Director", "Head of"],
    "manager": ["Manager", "Lead"],
    "ic": ["Engineer", "Designer", "Analyst", "Specialist"],
}


def register(mcp) -> None:
    @mcp.tool()
    def salesnav_build_list(
        titles: list[str] | None = None,
        seniority: str | None = None,
        industries: list[str] | None = None,
        company_keywords: list[str] | None = None,
        geo_urns: list[str] | None = None,
        extra_keywords: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Build a lead list without clicking filters.

        - titles: e.g. ["Head of Revenue","VP Sales"]
        - seniority: one of founder|c-level|vp|director|manager|ic
        - industries: LinkedIn industry URN codes (strings)
        - company_keywords: restrict to people at companies whose names match these
        - geo_urns: region URN ids (strings)
        """
        title_terms: list[str] = list(titles or [])
        if seniority:
            title_terms += SENIORITY_KEYWORDS.get(seniority.lower(), [])
        kw = " OR ".join(f'"{t}"' for t in title_terms) if title_terms else None
        if extra_keywords:
            kw = f"({kw}) {extra_keywords}" if kw else extra_keywords
        client = LinkedInClient.get()
        hits = client.search_people(
            keywords=kw,
            current_company=company_keywords,
            industries=industries,
            regions=geo_urns,
            limit=limit,
        )
        return hits

    @mcp.tool()
    def salesnav_account_list(
        industries: list[str] | None = None,
        size_ranges: list[str] | None = None,
        keywords: list[str] | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Build a target account list by industry, size, keywords.

        size_ranges examples: ["B","C"] (B=11-50, C=51-200, D=201-500, E=501-1000, F=1001-5000, G=5001-10000, H=10001+).
        """
        companies = LinkedInClient.get().search_companies(keywords=keywords, limit=limit)
        if industries:
            companies = [c for c in companies if c.get("industry") in industries]
        if size_ranges:
            companies = [c for c in companies if c.get("staffCountRange") in size_ranges]
        return companies
