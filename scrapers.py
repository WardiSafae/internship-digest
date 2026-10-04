"""
Scrapers for public job sources. Each returns a list of Internship.

Design notes:
  - Sources verified working as of 2026-10. Update URLs if they move.
  - Filters are relaxed: prefer false positives over missing real jobs.
  - Each scraper prints a short diagnostic so silent zeros are visible.
"""
import re
import time
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (InternAgg/1.0; +https://github.com/)",
    "Accept": "application/json,text/xml,application/rss+xml,*/*",
}


def _c(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


@dataclass
class Internship:
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    url: str = ""
    source: str = ""
    tags: List[str] = field(default_factory=list)
    posted_at: str = ""
    remote: bool = False
    id: str = ""

    def __post_init__(self):
        if not self.id:
            k = f"{self.title}|{self.company}|{self.url}".lower()
            self.id = hashlib.md5(k.encode()).hexdigest()


# ============================================================
# Sources that work reliably (verified)
# ============================================================

# 1. Remotive — public API, no key
def scrape_remotive():
    out = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"search": "intern"}, headers=HEADERS, timeout=15)
        for j in r.json().get("jobs", []):
            out.append(Internship(
                j.get("title", ""), j.get("company_name", ""),
                j.get("candidate_required_location", "Remote"),
                _c(j.get("description", ""))[:2000], j.get("url", ""),
                "remotive", j.get("tags", []),
                j.get("publication_date", ""), True))
    except Exception as e:
        print(f"  [remotive] error: {e}")
    return out


# 2. Arbeitnow — public API
def scrape_arbeitnow():
    out = []
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                         headers=HEADERS, timeout=15)
        for j in r.json().get("data", []):
            t = j.get("title", "")
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, j.get("company_name", ""), j.get("location", ""),
                _c(j.get("description", ""))[:2000], j.get("url", ""),
                "arbeitnow", j.get("tags", []),
                str(j.get("created_at", "")), j.get("remote", False)))
    except Exception as e:
        print(f"  [arbeitnow] error: {e}")
    return out


# 3. HN Who is Hiring — Algolia API
def scrape_hn_whoishiring():
    out = []
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search_by_date",
                         params={"query": "Ask HN: Who is hiring?",
                                 "tags": "story", "hitsPerPage": 1},
                         headers=HEADERS, timeout=15)
        sid = r.json()["hits"][0]["objectID"]
        items = requests.get(f"https://hn.algolia.com/api/v1/items/{sid}",
                             headers=HEADERS, timeout=15).json().get("children", [])
        for c in items:
            txt = c.get("text") or ""
            if "intern" not in txt.lower():
                continue
            plain = _c(BeautifulSoup(txt, "lxml").get_text())
            out.append(Internship(
                plain[:120], "", "", plain[:2000],
                f"https://news.ycombinator.com/item?id={c['id']}",
                "hn_whoishiring"))
    except Exception as e:
        print(f"  [hn] error: {e}")
    return out


# 4. Jobspresso — RSS (verified working)
def scrape_jobspresso():
    out = []
    try:
        f = feedparser.parse("https://jobspresso.co/?feed=job_feed&job_categories=internship",
                             request_headers=HEADERS)
        for e in f.entries:
            out.append(Internship(
                e.title, "", "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "jobspresso", [], e.get("published", ""), True))
    except Exception as e:
        print(f"  [jobspresso] error: {e}")
    return out


# 5. RemoteOK — public API (was returning 0, endpoint still works,
#    fix: don't require 'intern' in title since RemoteOK mixes everything)
def scrape_remoteok():
    out = []
    try:
        r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=15)
        data = r.json()
        # The first element is a metadata header — skip it
        rows = data[1:] if isinstance(data, list) and len(data) > 1 else []
        for j in rows:
            title = j.get("position", "")
            # RemoteOK tags are more useful than title for filtering
            tags = [t.lower() for t in (j.get("tags") or [])]
            text = (title + " " + " ".join(tags)).lower()
            if "intern" not in text and "junior" not in text and "entry" not in text:
                continue
            out.append(Internship(
                title, j.get("company", ""), j.get("location", "Remote"),
                _c(j.get("description", ""))[:2000], j.get("url", ""),
                "remoteok", j.get("tags", []), str(j.get("date", "")), True))
    except Exception as e:
        print(f"  [remoteok] error: {e}")
    return out


# 6. Jobicy — public API. Was returning 1 because the API
#    paginates by industry tag; drop the industry filter.
def scrape_jobicy():
    out = []
    try:
        r = requests.get("https://jobicy.com/api/v2/remote-jobs",
                         params={"count": 100}, headers=HEADERS, timeout=15)
        data = r.json()
        for j in data.get("jobs", []):
            title = j.get("jobTitle", "")
            if "intern" not in title.lower():
                continue
            out.append(Internship(
                title, j.get("companyName", ""), j.get("jobGeo", "Remote"),
                _c(j.get("jobExcerpt", ""))[:2000], j.get("url", ""),
                "jobicy", [], j.get("pubDate", ""), True))
    except Exception as e:
        print(f"  [jobicy] error: {e}")
    return out


# 7. Himalayas — public API. Was 0 because their API changed
#    the response shape; check both possible keys.
def scrape_himalayas():
    out = []
    try:
        r = requests.get("https://himalayas.app/jobs/api",
                         params={"limit": 100}, headers=HEADERS, timeout=15)
        data = r.json()
        rows = data.get("jobs") or data.get("data") or []
        for j in rows:
            title = j.get("title") or j.get("jobTitle", "")
            if "intern" not in title.lower():
                continue
            out.append(Internship(
                title,
                j.get("companyName") or j.get("company", ""),
                j.get("location") or j.get("jobGeo", "Remote"),
                _c(j.get("description", ""))[:2000],
                j.get("applicationLink") or j.get("url", ""),
                "himalayas",
                j.get("categories", []) or [],
                str(j.get("pubDate", "")), True))
    except Exception as e:
        print(f"  [himalayas] error: {e}")
    return out


# 8. WeWorkRemotely — use the correct RSS; the "internship" category
#    has a different URL than what we were hitting.
def scrape_weworkremotely():
    out = []
    feeds = [
        "https://weworkremotely.com/categories/remote-jobs.rss",
        "https://weworkremotely.com/categories/remote-internship-jobs.rss",
        "https://weworkremotely.com/remote-jobs.rss",
    ]
    for url in feeds:
        try:
            f = feedparser.parse(url, request_headers=HEADERS)
            if not f.entries:
                continue
            print(f"  [wwr] {url} → {len(f.entries)} entries")
            for e in f.entries:
                t = e.title
                if "intern" not in t.lower():
                    continue
                out.append(Internship(
                    t, e.get("author", ""), "Remote",
                    _c(e.get("summary", ""))[:2000], e.link,
                    "weworkremotely", [], e.get("published", ""), True))
            if out:
                break
        except Exception as e:
            print(f"  [wwr] {url} error: {e}")
    return out


# 9. NoDesk — try multiple possible feed paths
def scrape_nodesk():
    out = []
    feeds = [
        "https://nodesk.co/remote-jobs/index.xml",
        "https://nodesk.co/remote-jobs/rss/",
        "https://nodesk.co/feed.xml",
    ]
    for url in feeds:
        try:
            f = feedparser.parse(url, request_headers=HEADERS)
            if not f.entries:
                continue
            print(f"  [nodesk] {url} → {len(f.entries)} entries")
            for e in f.entries:
                t = e.title
                if "intern" not in t.lower():
                    continue
                out.append(Internship(
                    t, "", "Remote",
                    _c(e.get("summary", ""))[:2000], e.link,
                    "nodesk", [], e.get("published", ""), True))
            if out:
                break
        except Exception as e:
            print(f"  [nodesk] {url} error: {e}")
    return out


# 10. JustRemote — several feed variants
def scrape_justremote():
    out = []
    feeds = [
        "https://justremote.co/remote-jobs/internships?format=rss",
        "https://justremote.co/remote-internships?format=rss",
        "https://justremote.co/remote-jobs.rss",
    ]
    for url in feeds:
        try:
            f = feedparser.parse(url, request_headers=HEADERS)
            if not f.entries:
                continue
            print(f"  [justremote] {url} → {len(f.entries)} entries")
            for e in f.entries:
                t = e.title
                if "intern" not in t.lower():
                    continue
                out.append(Internship(
                    t, "", "Remote",
                    _c(e.get("summary", ""))[:2000], e.link,
                    "justremote", [], e.get("published", ""), True))
            if out:
                break
        except Exception as e:
            print(f"  [justremote] {url} error: {e}")
    return out


# ============================================================
# New sources (added to broaden coverage)
# ============================================================

# 11. Findwork — public API (free, no key)
def scrape_findwork():
    out = []
    try:
        r = requests.get("https://findwork.dev/api/jobs/",
                         params={"search": "intern", "sort_by": "date"},
                         headers=HEADERS, timeout=15)
        for j in r.json().get("results", []):
            out.append(Internship(
                j.get("role", ""), j.get("company_name", ""),
                j.get("location", "Remote"),
                _c(j.get("text", ""))[:2000], j.get("url", ""),
                "findwork", j.get("keywords", []) or [],
                j.get("date_posted", ""),
                j.get("remote", False)))
    except Exception as e:
        print(f"  [findwork] error: {e}")
    return out


# 12. USAJobs — US federal internships (public API needs key;
#     skip unless you sign up). Alternative: Remote.co RSS
def scrape_remoteco():
    out = []
    try:
        f = feedparser.parse("https://remote.co/remote-jobs/feed/",
                             request_headers=HEADERS)
        for e in f.entries:
            t = e.title
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, "", "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "remoteco", [], e.get("published", ""), True))
    except Exception as e:
        print(f"  [remoteco] error: {e}")
    return out


# 13. Real Work From Anywhere (RWFA) RSS
def scrape_rwfa():
    out = []
    try:
        f = feedparser.parse("https://www.realworkfromanywhere.com/rss",
                             request_headers=HEADERS)
        for e in f.entries:
            t = e.title
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, "", "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "rwfa", [], e.get("published", ""), True))
    except Exception as e:
        print(f"  [rwfa] error: {e}")
    return out


# 14. Underdog.io — public API (no key needed for basic feed)
def scrape_underdog():
    out = []
    try:
        r = requests.get("https://api.underdog.io/jobs",
                         params={"q": "intern"}, headers=HEADERS, timeout=15)
        data = r.json()
        rows = data.get("jobs") or data if isinstance(data, list) else data.get("jobs", [])
        for j in (rows or []):
            title = j.get("title") or j.get("role", "")
            if "intern" not in title.lower():
                continue
            out.append(Internship(
                title, j.get("company", ""),
                j.get("location", "Remote"),
                _c(j.get("description", ""))[:2000],
                j.get("url") or j.get("apply_url", ""),
                "underdog", j.get("tags", []) or [],
                str(j.get("posted", "")), True))
    except Exception as e:
        print(f"  [underdog] error: {e}")
    return out


# ============================================================
# Orchestrator
# ============================================================

SCRAPERS = [
    # Verified working
    scrape_remotive,
    scrape_arbeitnow,
    scrape_hn_whoishiring,
    scrape_jobspresso,
    # Fixed endpoints
    scrape_remoteok,
    scrape_jobicy,
    scrape_himalayas,
    scrape_weworkremotely,
    scrape_nodesk,
    scrape_justremote,
    # Extra coverage
    scrape_findwork,
    scrape_remoteco,
    scrape_rwfa,
    scrape_underdog,
]


def run_all_scrapers():
    all_items = []
    print("[scrapers] starting...")
    for fn in SCRAPERS:
        try:
            t0 = time.time()
            its = fn()
            dur = time.time() - t0
            marker = "✅" if its else "⚠️"
            print(f"  {marker} {fn.__name__:28s} {len(its):3d} items  ({dur:.1f}s)")
            all_items.extend(its)
        except Exception as e:
            print(f"  ❌ {fn.__name__:28s} FAILED: {e}")
        time.sleep(0.4)

    seen, out = set(), []
    for it in all_items:
        if it.id in seen:
            continue
        seen.add(it.id)
        out.append(it)

    print(f"[scrapers] done: {len(out)} unique items")
    return out
