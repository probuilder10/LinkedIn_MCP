"""Brand leads — import TikTok Shop / CSV brand lists and enrich via LinkedIn search."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from ..client import LinkedInClient
from ..storage.db import as_dict, as_list, get_db

_EMPTY_VALUES = {"", "Not found", "not found", "N/A", "n/a"}


def _clean(val: str | None) -> str | None:
    v = (val or "").strip()
    return None if v in _EMPTY_VALUES else v


def register(mcp) -> None:
    @mcp.tool()
    def import_brands_csv(
        csv_text: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Import a brand leads CSV into the database.

        Expected columns (Kalodata export format):
          Shop Name, Kalodata link, TikTok Profile, Webiste, Amazon,
          LinkedIn Company, Lead status, Welcome message, Follow up M1-M5.

        Pass the full CSV content as a string. Rows are upserted by Shop Name.
        Returns inserted/skipped counts and the total rows now in the table.
        """
        db = get_db()
        reader = csv.DictReader(io.StringIO(csv_text))
        inserted = skipped = 0
        for i, row in enumerate(reader):
            if limit is not None and i >= limit:
                break
            shop_name = _clean(row.get("Shop Name"))
            if not shop_name:
                skipped += 1
                continue
            website = _clean(row.get("Webiste") or row.get("Website"))
            amazon = _clean(row.get("Amazon"))
            tiktok = _clean(row.get("TikTok Profile"))
            li_company = _clean(row.get("LinkedIn Company"))
            kalodata = _clean(row.get("Kalodata link"))
            status = _clean(row.get("Lead status")) or "new"
            welcome = _clean(row.get("Welcome message"))
            db.execute(
                "INSERT INTO brand_leads"
                "(shop_name, kalodata_url, tiktok_profile, website, amazon_url,"
                " linkedin_company, lead_status, welcome_message) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(shop_name) DO UPDATE SET "
                "kalodata_url=excluded.kalodata_url,"
                "tiktok_profile=excluded.tiktok_profile,"
                "website=excluded.website,"
                "amazon_url=excluded.amazon_url,"
                "linkedin_company=COALESCE(excluded.linkedin_company, brand_leads.linkedin_company),"
                "lead_status=excluded.lead_status,"
                "welcome_message=COALESCE(excluded.welcome_message, brand_leads.welcome_message),"
                "updated_at=CURRENT_TIMESTAMP",
                (shop_name, kalodata, tiktok, website, amazon, li_company, status, welcome),
            )
            inserted += 1
        total = db.execute("SELECT COUNT(*) FROM brand_leads").fetchone()[0]
        return {"inserted": inserted, "skipped": skipped, "total_in_db": total}

    @mcp.tool()
    def list_brand_leads(
        status: str | None = None,
        has_website: bool | None = None,
        has_linkedin: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List brand leads. Filter by lead_status, presence of website, or LinkedIn company.

        Returns paginated rows plus the total count matching your filters.
        """
        db = get_db()
        where = "WHERE 1=1"
        params: list[Any] = []
        if status:
            where += " AND lead_status=?"
            params.append(status)
        if has_website is True:
            where += " AND website IS NOT NULL"
        elif has_website is False:
            where += " AND website IS NULL"
        if has_linkedin is True:
            where += " AND linkedin_company IS NOT NULL"
        elif has_linkedin is False:
            where += " AND linkedin_company IS NULL"
        total = db.execute(f"SELECT COUNT(*) FROM brand_leads {where}", params).fetchone()[0]
        rows = as_list(
            db.execute(
                f"SELECT * FROM brand_leads {where} ORDER BY id LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
        )
        return {"total": total, "offset": offset, "limit": limit, "rows": rows}

    @mcp.tool()
    def find_brand_contacts(
        brand_id: int,
        icp_name: str | None = None,
        titles: list[str] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Search LinkedIn for a brand's company page and its key decision-makers.

        Looks up the brand by brand_id, searches LinkedIn for the company by name,
        then searches people at that company with the given titles (defaults:
        Founder, CEO, CMO, Marketing Director). Scores against icp_name if provided.
        Stores found people in the prospects table and updates the brand's
        linkedin_company field.
        """
        db = get_db()
        brand_row = db.execute("SELECT * FROM brand_leads WHERE id=?", (brand_id,)).fetchone()
        if not brand_row:
            raise ValueError(f"Brand {brand_id} not found")
        brand = as_dict(brand_row)

        client = LinkedInClient.get()
        search_titles = titles or ["Founder", "CEO", "CMO", "Marketing Director", "Head of Marketing"]

        companies = client.search_companies(keywords=[brand["shop_name"]], limit=5)
        if not companies:
            return {
                "brand_id": brand_id,
                "shop_name": brand["shop_name"],
                "companies_found": 0,
                "prospects": [],
            }

        top = companies[0]
        # entityUrn looks like "urn:li:company:12345" — we need the numeric part
        entity_urn = top.get("entityUrn", "")
        company_id = entity_urn.split(":")[-1] if entity_urn else top.get("public_id", "")
        company_name = top.get("name") or top.get("title") or brand["shop_name"]

        db.execute(
            "UPDATE brand_leads SET linkedin_company=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (company_id, brand_id),
        )

        icp_row = None
        if icp_name:
            icp_row = db.execute("SELECT * FROM icp WHERE name=?", (icp_name,)).fetchone()

        # Search people filtered to this company; title keyword covers all roles at once
        title_keywords = " ".join(search_titles)
        people = client.search_people(
            keywords=title_keywords,
            current_company=[company_id] if company_id else None,
            limit=limit,
        )

        from .scoring import _score

        prospects_out: list[dict[str, Any]] = []
        for person in people:
            public_id = person.get("publicIdentifier") or person.get("public_id")
            if not public_id:
                continue
            try:
                profile = client.get_profile(public_id=public_id)
            except Exception:
                profile = person

            score = 0.0
            breakdown: dict[str, Any] = {}
            if icp_row:
                score, breakdown = _score(profile, icp_row)

            exp = (profile.get("experience") or [{}])[0]
            db.execute(
                "INSERT INTO prospects"
                "(public_id, urn_id, full_name, headline, company, title,"
                " location, industry, score, raw, icp_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(public_id) DO UPDATE SET"
                " score=excluded.score, updated_at=CURRENT_TIMESTAMP",
                (
                    public_id,
                    profile.get("entityUrn"),
                    f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
                    profile.get("headline"),
                    exp.get("companyName") or company_name,
                    exp.get("title"),
                    profile.get("locationName"),
                    profile.get("industryName"),
                    score,
                    json.dumps(profile),
                    icp_row["id"] if icp_row else None,
                ),
            )
            prospects_out.append(
                {
                    "public_id": public_id,
                    "name": f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip(),
                    "title": exp.get("title"),
                    "score": score,
                    "breakdown": breakdown,
                }
            )

        return {
            "brand_id": brand_id,
            "shop_name": brand["shop_name"],
            "linkedin_company_id": company_id,
            "linkedin_company_name": company_name,
            "companies_found": len(companies),
            "prospects_added": len(prospects_out),
            "prospects": prospects_out,
        }

    @mcp.tool()
    def update_brand_lead(
        brand_id: int,
        linkedin_company: str | None = None,
        lead_status: str | None = None,
        welcome_message: str | None = None,
    ) -> dict[str, Any]:
        """Update fields on a brand lead (LinkedIn company ID, status, welcome message)."""
        db = get_db()
        sets: list[str] = []
        params: list[Any] = []
        if linkedin_company is not None:
            sets.append("linkedin_company=?")
            params.append(linkedin_company)
        if lead_status is not None:
            sets.append("lead_status=?")
            params.append(lead_status)
        if welcome_message is not None:
            sets.append("welcome_message=?")
            params.append(welcome_message)
        if not sets:
            raise ValueError("Nothing to update — pass at least one field")
        sets.append("updated_at=CURRENT_TIMESTAMP")
        params.append(brand_id)
        db.execute(f"UPDATE brand_leads SET {', '.join(sets)} WHERE id=?", params)
        return as_dict(db.execute("SELECT * FROM brand_leads WHERE id=?", (brand_id,)).fetchone()) or {}

    @mcp.tool()
    def brand_lead_stats() -> dict[str, Any]:
        """Return summary statistics for the brand leads table."""
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM brand_leads").fetchone()[0]
        if total == 0:
            return {"total": 0, "by_status": {}, "with_linkedin_company": 0, "with_website": 0, "with_tiktok": 0}
        by_status = dict(
            db.execute("SELECT lead_status, COUNT(*) FROM brand_leads GROUP BY lead_status").fetchall()
        )
        with_li = db.execute(
            "SELECT COUNT(*) FROM brand_leads WHERE linkedin_company IS NOT NULL"
        ).fetchone()[0]
        with_web = db.execute(
            "SELECT COUNT(*) FROM brand_leads WHERE website IS NOT NULL"
        ).fetchone()[0]
        with_tt = db.execute(
            "SELECT COUNT(*) FROM brand_leads WHERE tiktok_profile IS NOT NULL"
        ).fetchone()[0]
        return {
            "total": total,
            "by_status": by_status,
            "with_linkedin_company": with_li,
            "with_website": with_web,
            "with_tiktok": with_tt,
        }
