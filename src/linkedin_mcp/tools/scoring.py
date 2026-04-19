"""ICP management and prospect scoring."""

from __future__ import annotations

from typing import Any

from rapidfuzz import fuzz

from ..client import LinkedInClient
from ..storage.db import as_dict, as_list, get_db, jdump, jload


def register(mcp) -> None:
    @mcp.tool()
    def create_icp(
        name: str,
        description: str,
        titles: list[str] | None = None,
        seniorities: list[str] | None = None,
        industries: list[str] | None = None,
        company_sizes: list[str] | None = None,
        geographies: list[str] | None = None,
        keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register an Ideal Customer Profile used by scoring and campaigns."""
        db = get_db()
        cur = db.execute(
            "INSERT INTO icp(name, description, titles, seniorities, industries, company_sizes, geographies, keywords) "
            "VALUES(?,?,?,?,?,?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET description=excluded.description, titles=excluded.titles, "
            "seniorities=excluded.seniorities, industries=excluded.industries, "
            "company_sizes=excluded.company_sizes, geographies=excluded.geographies, keywords=excluded.keywords",
            (
                name,
                description,
                jdump(titles or []),
                jdump(seniorities or []),
                jdump(industries or []),
                jdump(company_sizes or []),
                jdump(geographies or []),
                jdump(keywords or []),
            ),
        )
        row = db.execute("SELECT * FROM icp WHERE name=?", (name,)).fetchone()
        icp = as_dict(row) or {}
        for k in ("titles", "seniorities", "industries", "company_sizes", "geographies", "keywords"):
            icp[k] = jload(icp.get(k))
        icp["id"] = icp.get("id", cur.lastrowid)
        return icp

    @mcp.tool()
    def list_icps() -> list[dict[str, Any]]:
        """List ICPs."""
        db = get_db()
        rows = db.execute("SELECT * FROM icp ORDER BY id").fetchall()
        out = as_list(rows)
        for r in out:
            for k in ("titles", "seniorities", "industries", "company_sizes", "geographies", "keywords"):
                r[k] = jload(r.get(k))
        return out

    @mcp.tool()
    def score_prospect(public_id: str, icp_name: str) -> dict[str, Any]:
        """Fetch a prospect and score them 0..100 against the ICP. Stores them if not already tracked."""
        db = get_db()
        icp = db.execute("SELECT * FROM icp WHERE name=?", (icp_name,)).fetchone()
        if not icp:
            raise ValueError(f"ICP '{icp_name}' not found")
        client = LinkedInClient.get()
        profile = client.get_profile(public_id=public_id)

        score, breakdown = _score(profile, icp)

        exp = (profile.get("experience") or [{}])[0]
        db.execute(
            "INSERT INTO prospects(public_id, urn_id, full_name, headline, company, title, location, industry, score, raw, icp_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(public_id) DO UPDATE SET "
            "full_name=excluded.full_name, headline=excluded.headline, company=excluded.company, "
            "title=excluded.title, location=excluded.location, industry=excluded.industry, "
            "score=excluded.score, raw=excluded.raw, icp_id=excluded.icp_id, "
            "updated_at=CURRENT_TIMESTAMP",
            (
                public_id,
                profile.get("entityUrn"),
                f"{profile.get('firstName','')} {profile.get('lastName','')}".strip(),
                profile.get("headline"),
                exp.get("companyName"),
                exp.get("title"),
                profile.get("locationName"),
                profile.get("industryName"),
                score,
                jdump(profile),
                icp["id"],
            ),
        )
        return {"public_id": public_id, "score": score, "breakdown": breakdown}

    @mcp.tool()
    def list_prospects(
        icp_name: str | None = None,
        min_score: float = 0.0,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query stored prospects."""
        db = get_db()
        q = "SELECT p.* FROM prospects p LEFT JOIN icp i ON p.icp_id=i.id WHERE p.score >= ?"
        params: list[Any] = [min_score]
        if icp_name:
            q += " AND i.name=?"
            params.append(icp_name)
        if status:
            q += " AND p.status=?"
            params.append(status)
        q += " ORDER BY p.score DESC LIMIT ?"
        params.append(limit)
        return as_list(db.execute(q, params).fetchall())

    @mcp.tool()
    def enrich_company(public_id: str) -> dict[str, Any]:
        """Attach company data (industry, size, headcount, description) for quick ICP fit check."""
        return LinkedInClient.get().get_company(public_id)


def _score(profile: dict, icp) -> tuple[float, dict]:
    breakdown: dict[str, Any] = {}
    score = 0.0
    exp = (profile.get("experience") or [{}])[0]
    title = (exp.get("title") or "").lower()
    headline = (profile.get("headline") or "").lower()
    industry = (profile.get("industryName") or "").lower()
    location = (profile.get("locationName") or "").lower()

    titles = jload(icp["titles"]) or []
    if titles:
        best = max((fuzz.partial_ratio(t.lower(), title + " " + headline) for t in titles), default=0)
        breakdown["title_match"] = best
        score += (best / 100) * 40

    industries = jload(icp["industries"]) or []
    if industries:
        hit = any(i.lower() in industry for i in industries)
        breakdown["industry_match"] = 100 if hit else 0
        score += 20 if hit else 0

    keywords = jload(icp["keywords"]) or []
    if keywords:
        text = " ".join(
            [profile.get("summary") or "", headline, title, " ".join(profile.get("skills", []) or [])]
        ).lower()
        hits = sum(1 for k in keywords if k.lower() in text)
        breakdown["keyword_hits"] = hits
        score += min(hits * 5, 20)

    geos = jload(icp["geographies"]) or []
    if geos:
        hit = any(g.lower() in location for g in geos)
        breakdown["geo_match"] = 100 if hit else 0
        score += 10 if hit else 0

    seniorities = jload(icp["seniorities"]) or []
    if seniorities:
        sen_text = title + " " + headline
        hit = any(s.lower() in sen_text for s in seniorities)
        breakdown["seniority_match"] = 100 if hit else 0
        score += 10 if hit else 0

    return round(min(score, 100), 2), breakdown
