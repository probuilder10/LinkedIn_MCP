"""Tests for brand leads import and LinkedIn enrichment."""

import textwrap

import pytest


SAMPLE_CSV = textwrap.dedent("""\
    Shop Name,Kalodata link,TikTok Profile,Webiste,Amazon,LinkedIn Company,Lead status,Welcome message,Follow up M1
    Acme Beauty,https://kalodata.com/shop/1,https://tiktok.com/@acmebeauty,https://acmebeauty.com,Not found,,new,,
    FooStore,https://kalodata.com/shop/2,,Not found,Not found,,new,,
    BarBrand,,https://tiktok.com/@barbrand,https://barbrand.store,https://amazon.com/stores/barbrand,,new,,
    ,,,,,,new,,
""")


def test_import_basic(tools):
    result = tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    assert result["inserted"] == 3  # EmptyName row is skipped
    assert result["skipped"] == 1
    assert result["total_in_db"] == 3


def test_import_idempotent(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    result = tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    assert result["total_in_db"] == 3  # no duplicates


def test_import_limit(tools):
    result = tools["import_brands_csv"](csv_text=SAMPLE_CSV, limit=1)
    assert result["inserted"] == 1
    assert result["total_in_db"] == 1


def test_import_cleans_not_found(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    listed = tools["list_brand_leads"]()
    foo = next(r for r in listed["rows"] if r["shop_name"] == "FooStore")
    assert foo["website"] is None
    assert foo["amazon_url"] is None
    acme = next(r for r in listed["rows"] if r["shop_name"] == "Acme Beauty")
    assert acme["website"] == "https://acmebeauty.com"
    assert acme["tiktok_profile"] == "https://tiktok.com/@acmebeauty"


def test_list_filters(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    with_web = tools["list_brand_leads"](has_website=True)
    assert all(r["website"] is not None for r in with_web["rows"])

    without_web = tools["list_brand_leads"](has_website=False)
    assert all(r["website"] is None for r in without_web["rows"])


def test_list_pagination(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    page1 = tools["list_brand_leads"](limit=2, offset=0)
    page2 = tools["list_brand_leads"](limit=2, offset=2)
    assert page1["total"] == 3
    assert len(page1["rows"]) == 2
    assert len(page2["rows"]) == 1


def test_brand_lead_stats(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    stats = tools["brand_lead_stats"]()
    assert stats["total"] == 3
    assert stats["by_status"]["new"] == 3
    assert stats["with_website"] == 2
    assert stats["with_tiktok"] == 2


def test_brand_lead_stats_empty(tools):
    stats = tools["brand_lead_stats"]()
    assert stats["total"] == 0


def test_update_brand_lead(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    listed = tools["list_brand_leads"]()
    brand_id = listed["rows"][0]["id"]

    updated = tools["update_brand_lead"](brand_id=brand_id, lead_status="contacted", linkedin_company="999")
    assert updated["lead_status"] == "contacted"
    assert updated["linkedin_company"] == "999"


def test_update_brand_lead_nothing(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    listed = tools["list_brand_leads"]()
    brand_id = listed["rows"][0]["id"]
    with pytest.raises(ValueError):
        tools["update_brand_lead"](brand_id=brand_id)


def test_find_brand_contacts(tools, fake_li):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    listed = tools["list_brand_leads"]()
    brand_id = listed["rows"][0]["id"]

    result = tools["find_brand_contacts"](brand_id=brand_id, limit=3)
    assert result["brand_id"] == brand_id
    assert result["linkedin_company_id"] == "1234"  # extracted from urn:li:company:1234
    assert result["linkedin_company_name"] == "Acme"
    assert result["prospects_added"] >= 1

    # brand's linkedin_company should be updated in DB
    after = tools["list_brand_leads"]()
    row = next(r for r in after["rows"] if r["id"] == brand_id)
    assert row["linkedin_company"] == "1234"

    # prospect should be stored
    from linkedin_mcp.storage.db import get_db
    db = get_db()
    count = db.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    assert count >= 1


def test_find_brand_contacts_with_icp(tools):
    tools["import_brands_csv"](csv_text=SAMPLE_CSV)
    tools["create_icp"](
        name="ecom_founders",
        description="Ecommerce founders",
        titles=["VP Sales"],
        industries=["Software Development"],
        keywords=["SaaS"],
    )
    listed = tools["list_brand_leads"]()
    brand_id = listed["rows"][0]["id"]
    result = tools["find_brand_contacts"](brand_id=brand_id, icp_name="ecom_founders", limit=2)
    assert result["prospects_added"] >= 1
    assert result["prospects"][0]["score"] > 0


def test_find_brand_contacts_not_found(tools):
    with pytest.raises(ValueError, match="Brand 999 not found"):
        tools["find_brand_contacts"](brand_id=999)
