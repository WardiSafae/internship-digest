"""Offline tests: every spider is fed a small fixture, no network needed.

    pip install pytest
    pytest -q
"""
import hashlib

import pytest
from scrapy import Request
from scrapy.exceptions import DropItem
from scrapy.http import HtmlResponse, TextResponse, XmlResponse
from scrapy.utils.test import get_crawler

from internship_scrapy.items import InternshipItem
from internship_scrapy.pipelines import CleanPipeline, DedupPipeline, IdPipeline
from internship_scrapy.spiders.arbeitnow import ArbeitnowSpider
from internship_scrapy.spiders.himalayas import HimalayasSpider
from internship_scrapy.spiders.hn_whoishiring import HNWhoIsHiringSpider
from internship_scrapy.spiders.jobicy import JobicySpider
from internship_scrapy.spiders.jobspresso import JobspressoSpider
from internship_scrapy.spiders.marocannonces import MarocAnnoncesSpider
from internship_scrapy.spiders.rekrute import RekruteSpider
from internship_scrapy.spiders.remoteok import RemoteOKSpider
from internship_scrapy.spiders.remotive import RemotiveSpider
from internship_scrapy.spiders.weworkremotely import WeWorkRemotelySpider
from internship_scrapy.spiders.working_nomads import WorkingNomadsSpider
from tests import fixtures as F


def spider(cls, **kw):
    return cls.from_crawler(get_crawler(cls), **kw)


def response(url, body, kind="text"):
    cls = {"text": TextResponse, "html": HtmlResponse, "xml": XmlResponse}[kind]
    return cls(url=url, body=body.encode(), encoding="utf-8", request=Request(url))


def processed(items):
    """Run items through the same cleaning + id steps as the real pipeline."""
    return [IdPipeline().process_item(CleanPipeline().process_item(i)) for i in items]


# ── JSON APIs ───────────────────────────────────────────────────────────
def test_remotive_maps_fields_and_cleans_html():
    items = processed(spider(RemotiveSpider).parse(response("https://x/", F.REMOTIVE)))
    assert [i["title"] for i in items] == ["Data Science Intern", "ML Intern"]
    first = items[0]
    assert first["company"] == "Acme" and first["remote"] is True
    assert first["description"] == "Work on NLP models & pipelines."   # tags/entities/newlines gone
    assert items[1]["location"] == "Remote"                            # default when missing


@pytest.mark.parametrize("cls,body,expected", [
    (ArbeitnowSpider, F.ARBEITNOW, ["Software Engineering Intern (Full-Stack)"]),
    (RemoteOKSpider, F.REMOTEOK, ["Junior Data Analyst", "Backend Engineer"]),  # 2nd matches via tag "intern"
    (JobicySpider, F.JOBICY, ["Marketing Intern"]),
    (HimalayasSpider, F.HIMALAYAS, ["Graduate Software Engineer"]),
    (WorkingNomadsSpider, F.WORKING_NOMADS, ["Trainee Recruiter"]),
])
def test_entry_level_filter(cls, body, expected):
    items = list(spider(cls).parse(response("https://x/", body)))
    assert [i["title"] for i in items] == expected


def test_remoteok_skips_legal_metadata_row():
    s = spider(RemoteOKSpider)
    list(s.parse(response("https://x/", F.REMOTEOK)))
    assert s.crawler.stats.get_value("source/rows_seen") == 3   # 4 rows minus the legal one


def test_hn_chain_search_then_thread():
    s = spider(HNWhoIsHiringSpider)
    (req,) = list(s.parse(response("https://x/", F.HN_SEARCH)))
    assert req.url.endswith("/items/424242")
    items = processed(s.parse_thread(response(req.url, F.HN_THREAD)))
    assert len(items) == 1                                   # "Staff Engineer" has no entry-level term
    assert items[0]["url"] == "https://news.ycombinator.com/item?id=1001"
    assert items[0]["title"].startswith("Acme | ML Intern | REMOTE")
    assert "<" not in items[0]["description"]


# ── RSS ─────────────────────────────────────────────────────────────────
def test_jobspresso_rss_with_cdata():
    (it,) = processed(spider(JobspressoSpider).parse(response("https://x/", F.JOBSPRESSO, "xml")))
    assert it["title"] == "Product Intern" and it["url"] == "https://jobspresso.co/job/1"
    assert it["description"] == "Join us"                    # CDATA HTML stripped
    assert it["posted_at"].startswith("Mon, 20 Oct 2026")


def test_weworkremotely_falls_back_to_second_feed():
    s = spider(WeWorkRemotelySpider)
    (req,) = list(s.parse(response("https://x/1", F.WWR_EMPTY, "xml"), next_idx=1))
    assert isinstance(req, Request) and "categories" in req.url
    (it,) = list(s.parse(response(req.url, F.WWR_FALLBACK, "xml"), next_idx=2))
    assert it["title"] == "Junior Designer" and it["company"] == "Lambda"


# ── HTML ────────────────────────────────────────────────────────────────
def test_rekrute_filters_noise_and_detects_city_and_tags():
    items = list(spider(RekruteSpider).parse(
        response("https://www.rekrute.com/offres.html?s=1&p=1&o=1", F.REKRUTE, "html")))
    titles = [i["title"] for i in items]
    assert titles == ["Stage Data Analyst | Casablanca (Maroc)",
                      "Conseiller Client (F/H) - Service client - Rabat"]
    # dropped: "Lancer 4K" (button), "Court" (<8 chars), "...Senior Confirmé" (seniority)
    assert items[0]["location"] == "Casablanca" and "stage" in items[0]["tags"]
    assert items[1]["location"] == "Rabat" and "cdi" in items[1]["tags"]
    assert items[0]["url"].startswith("https://www.rekrute.com/offre-emploi-")


def test_rekrute_fallback_selector_when_class_disappears():
    items = list(spider(RekruteSpider).parse(
        response("https://www.rekrute.com/offres.html", F.REKRUTE_NO_CLASS, "html")))
    assert [i["title"] for i in items] == ["Stage Développeur Web Fès"]
    assert items[0]["location"] == "Fès"


def test_rekrute_requests_n_pages():
    s = spider(RekruteSpider, pages=4)
    import asyncio

    async def collect():
        return [r async for r in s.start()]
    assert len(asyncio.run(collect())) == 4


def test_marocannonces_builds_absolute_urls_and_extracts_city_company():
    s = spider(MarocAnnoncesSpider)
    items = list(s.parse(response("https://www.marocannonces.com/maroc/emploi.html",
                                  F.MAROCANNONCES, "html"), next_idx=1))
    assert len(items) == 2                                   # "ok" (too short) and the menu link are ignored
    assert all(i["url"].startswith("https://www.marocannonces.com/categorie/309/") for i in items)
    paie = items[0]
    assert paie["location"] == "Berrechid" and paie["company"] == "RH Services"


def test_marocannonces_falls_back_to_second_page():
    s = spider(MarocAnnoncesSpider)
    (req,) = list(s.parse(response("https://x/1", F.MAROCANNONCES_EMPTY, "html"), next_idx=1))
    assert isinstance(req, Request) and "Offres-emploi.html" in req.url


# ── Pipelines ───────────────────────────────────────────────────────────
def make(**kw):
    base = dict(title="T", company="C", url="https://u", description="", tags=[],
                location="", posted_at="", remote=False, source="s")
    base.update(kw)
    return InternshipItem(**base)


def test_id_is_md5_of_lowercased_title_company_url():
    item = IdPipeline().process_item(make(title="Data Intern", company="ACME", url="https://U/1"))
    assert item["id"] == hashlib.md5(b"data intern|acme|https://u/1").hexdigest()


def test_clean_pipeline_drops_items_without_title_or_url():
    with pytest.raises(DropItem):
        CleanPipeline().process_item(make(title=""))
    with pytest.raises(DropItem):
        CleanPipeline().process_item(make(url=""))


def test_clean_pipeline_caps_description_and_normalises_types():
    item = CleanPipeline().process_item(make(description="<p>" + "word " * 1000 + "</p>",
                                             tags=None, remote=1, company=None))
    assert len(item["description"]) <= 2000 and "<" not in item["description"]
    assert item["tags"] == [] and item["remote"] is True and item["company"] == ""


def test_dedup_pipeline_drops_second_copy():
    p = DedupPipeline()
    a = IdPipeline().process_item(make())
    p.process_item(a)
    with pytest.raises(DropItem):
        p.process_item(IdPipeline().process_item(make()))
