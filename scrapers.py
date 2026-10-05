"""
Scrapers for public job sources. Each returns a list of Internship.

Design notes:
  - Every network call has a hard timeout. No source can hang the job.
  - Filters are relaxed: entry-level titles match several keywords.
  - Dead sources removed. Add new ones at the bottom of SCRAPERS.
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
    "User-Agent": "Mozilla/5.0 (InternAgg/1.0)",
    "Accept": "application/json,text/xml,application/rss+xml,*/*",
}

ENTRY_TERMS = ("intern", "graduate", "junior", "entry", "trainee", "apprentice")


def _c(t):
    return re.sub(r"\s+", " ", (t or "")).strip()


def _is_entry_level(text):
    t = (text or "").lower()
    return any(term in t for term in ENTRY_TERMS)


def _fetch_feed(url, timeout=8):
    """Fetch RSS with a hard timeout. Returns feedparser object or None."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return None
        return feedparser.parse(r.content)
    except Exception as e:
        print(f"  [feed] {url} -> {type(e).__name__}")
        return None


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


# ----------------------------------------------------------------
# Sources
# ----------------------------------------------------------------

def scrape_remotive():
    out = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"search": "intern"}, headers=HEADERS, timeout=8)
        for j in r.json().get("jobs", []):
            title = j.get("title", "")
            if not _is_entry_level(title):
                continue
            out.append(Internship(
                title, j.get("company_name", ""),
                j.get("candidate_required_location", "Remote"),
                _c(j.get("description", ""))[:2000], j.get("url", ""),
                "remotive", j.get("tags", []),
                j.get("publication_date", ""), True))
    except Exception as e:
        print(f"  [remotive] {type(e).__name__}")
    return out


def scrape_arbeitnow():
    out = []
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api",
                         headers=HEADERS, timeout=8)
        for j in r.json().get("data", []):
            t = j.get("title", "")
            if not _is_entry_level(t):
                continue
            out.append(Internship(
                t, j.get("company_name", ""), j.get("location", ""),
                _c(j.get("description", ""))[:2000], j.get("url", ""),
                "arbeitnow", j.get("tags", []),
                str(j.get("created_at", "")), j.get("remote", False)))
    except Exception as e:
        print(f"  [arbeitnow] {type(e).__name__}")
    return out


def scrape_hn_whoishiring():
    out = []
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search_by_date",
                         params={"query": "Ask HN: Who is hiring?",
                                 "tags": "story", "hitsPerPage": 1},
                         headers=HEADERS, timeout=8)
        sid = r.json()["hits"][0]["objectID"]
        items = requests.get(f"https://hn.algolia.com/api/v1/items/{sid}",
                             headers=HEADERS, timeout=8).json().get("children", [])
        for c in items:
            txt = c.get("text") or ""
            if not _is_entry_level(txt):
                continue
            plain = _c(BeautifulSoup(txt, "lxml").get_text())
            out.append(Internship(
                plain[:120], "", "", plain[:2000],
                f"https://news.ycombinator.com/item?id={c['id']}",
                "hn_whoishiring"))
    except Exception as e:
        print(f"  [hn] {type(e).__name__}")
    return out


def scrape_jobspresso():
    out = []
    f = _fetch_feed("https://jobspresso.co/?feed=job_feed&job_categories=internship")
    if not f:
        return out
    for e in f.entries:
        out.append(Internship(
            e.title, "", "Remote",
            _c(e.get("summary", ""))[:2000], e.link,
            "jobspresso", [], e.get("published", ""), True))
    return out


def scrape_remoteok():
    out = []
    try:
        r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=8)
        data = r.json()
        rows = data[1:] if isinstance(data, list) and len(data) > 1 else []
        for j in rows:
            title = j.get("position", "")
            tags = [t.lower() for t in (j.get("tags") or [])]
            text = (title + " " + " ".join(tags)).lower()
            if not _is_entry_level(text):
                continue
            out.append(Internship(
                title, j.get("company", ""), j.get("location", "Remote"),
                _c(j.get("description", ""))[:2000], j.get("url", ""),
                "remoteok", j.get("tags", []), str(j.get("date", "")), True))
    except Exception as e:
        print(f"  [remoteok] {type(e).__name__}")
    return out


def scrape_jobicy():
    out = []
    try:
        r = requests.get("https://jobicy.com/api/v2/remote-jobs",
                         params={"count": 100}, headers=HEADERS, timeout=8)
        for j in r.json().get("jobs", []):
            title = j.get("jobTitle", "")
            if not _is_entry_level(title):
                continue
            out.append(Internship(
                title, j.get("companyName", ""), j.get("jobGeo", "Remote"),
                _c(j.get("jobExcerpt", ""))[:2000], j.get("url", ""),
                "jobicy", [], j.get("pubDate", ""), True))
    except Exception as e:
        print(f"  [jobicy] {type(e).__name__}")
    return out


def scrape_himalayas():
    out = []
    try:
        r = requests.get("https://himalayas.app/jobs/api",
                         params={"limit": 100}, headers=HEADERS, timeout=8)
        data = r.json()
        rows = data.get("jobs") or data.get("data") or []
        for j in rows:
            title = j.get("title") or j.get("jobTitle", "")
            if not _is_entry_level(title):
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
        print(f"  [himalayas] {type(e).__name__}")
    return out


def scrape_weworkremotely():
    out = []
    for url in [
        "https://weworkremotely.com/categories/remote-jobs.rss",
        "https://weworkremotely.com/categories/remote-internship-jobs.rss",
    ]:
        f = _fetch_feed(url)
        if not f or not f.entries:
            continue
        print(f"  [wwr] {url} -> {len(f.entries)} entries")
        for e in f.entries:
            t = e.title
            if not _is_entry_level(t):
                continue
            out.append(Internship(
                t, e.get("author", ""), "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "weworkremotely", [], e.get("published", ""), True))
        if out:
            break
    return out


def scrape_remoteco():
    out = []
    f = _fetch_feed("https://remote.co/remote-jobs/feed/")
    if not f:
        return out
    for e in f.entries:
        t = e.title
        if not _is_entry_level(t):
            continue
        out.append(Internship(
            t, "", "Remote",
            _c(e.get("summary", ""))[:2000], e.link,
            "remoteco", [], e.get("published", ""), True))
    return out


def scrape_rwfa():
    out = []
    f = _fetch_feed("https://www.realworkfromanywhere.com/rss")
    if not f:
        return out
    for e in f.entries:
        t = e.title
        if not _is_entry_level(t):
            continue
        out.append(Internship(
            t, "", "Remote",
            _c(e.get("summary", ""))[:2000], e.link,
            "rwfa", [], e.get("published", ""), True))
    return out


SCRAPERS = [
    scrape_remotive,
    scrape_arbeitnow,
    scrape_hn_whoishiring,
    scrape_jobspresso,
    scrape_remoteok,
    scrape_jobicy,
    scrape_himalayas,
    scrape_weworkremotely,
    scrape_remoteco,
    scrape_rwfa,
]


def run_all_scrapers(global_timeout=90):
    all_items = []
    print("[scrapers] starting...")
    start = time.time()
    for fn in SCRAPERS:
        if time.time() - start > global_timeout:
            print(f"[scrapers] time budget exceeded ({global_timeout}s), stopping early")
            break
        try:
            t0 = time.time()
            its = fn()
            dur = time.time() - t0
            marker = "OK" if its else "--"
            print(f"  {marker} {fn.__name__:28s} {len(its):3d} items  ({dur:.1f}s)")
            all_items.extend(its)
        except Exception as e:
            print(f"  ERR {fn.__name__:28s} FAILED: {type(e).__name__}: {e}")
        time.sleep(0.3)

    seen, out = set(), []
    for it in all_items:
        if it.id in seen:
            continue
        seen.add(it.id)
        out.append(it)

    print(f"[scrapers] done: {len(out)} unique items in {time.time()-start:.1f}s")
    return out
