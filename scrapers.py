"""
Scrapers for 10 public job sources. Each returns a list of Internship.
"""
import re
import time
import hashlib
import requests
import feedparser
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List

HEADERS = {"User-Agent": "Mozilla/5.0 (InternAgg/1.0)"}


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


# 1. Remotive
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
        print("remotive", e)
    return out


# 2. Arbeitnow
def scrape_arbeitnow():
    out = []
    try:
        r = requests.get("https://www.arbeitnow.com/api/job-board-api", timeout=15)
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
        print("arbeitnow", e)
    return out


# 3. HackerNews Who is Hiring
def scrape_hn_whoishiring():
    out = []
    try:
        r = requests.get("https://hn.algolia.com/api/v1/search_by_date",
                         params={"query": "Ask HN: Who is hiring?",
                                 "tags": "story", "hitsPerPage": 1}, timeout=15)
        sid = r.json()["hits"][0]["objectID"]
        items = requests.get(f"https://hn.algolia.com/api/v1/items/{sid}",
                             timeout=15).json().get("children", [])
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
        print("hn", e)
    return out


# 4. RemoteOK
def scrape_remoteok():
    out = []
    try:
        r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=15)
        data = r.json()
        for j in data[1:]:
            t = j.get("position", "")
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, j.get("company", ""), j.get("location", "Remote"),
                _c(j.get("description", ""))[:2000], j.get("url", ""),
                "remoteok", j.get("tags", []), str(j.get("date", "")), True))
    except Exception as e:
        print("remoteok", e)
    return out


# 5. Jobicy
def scrape_jobicy():
    out = []
    try:
        r = requests.get("https://jobicy.com/api/v2/remote-jobs",
                         params={"count": 50}, headers=HEADERS, timeout=15)
        for j in r.json().get("jobs", []):
            t = j.get("jobTitle", "")
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, j.get("companyName", ""), j.get("jobGeo", "Remote"),
                _c(j.get("jobExcerpt", ""))[:2000], j.get("url", ""),
                "jobicy", [], j.get("pubDate", ""), True))
    except Exception as e:
        print("jobicy", e)
    return out


# 6. Himalayas
def scrape_himalayas():
    out = []
    try:
        r = requests.get("https://himalayas.app/jobs/api",
                         params={"limit": 50}, headers=HEADERS, timeout=15)
        for j in r.json().get("jobs", []):
            t = j.get("title", "")
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, j.get("companyName", ""), j.get("location", "Remote"),
                _c(j.get("description", ""))[:2000],
                j.get("applicationLink", ""), "himalayas",
                j.get("categories", []) or [], str(j.get("pubDate", "")), True))
    except Exception as e:
        print("himalayas", e)
    return out


# 7. WeWorkRemotely
def scrape_weworkremotely():
    out = []
    try:
        f = feedparser.parse("https://weworkremotely.com/categories/remote-jobs.rss")
        for e in f.entries:
            t = e.title
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, e.get("author", ""), "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "weworkremotely", [], e.get("published", ""), True))
    except Exception as e:
        print("wwr", e)
    return out


# 8. Jobspresso
def scrape_jobspresso():
    out = []
    try:
        f = feedparser.parse("https://jobspresso.co/?feed=job_feed&job_categories=internship")
        for e in f.entries:
            out.append(Internship(
                e.title, "", "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "jobspresso", [], e.get("published", ""), True))
    except Exception as e:
        print("jobspresso", e)
    return out


# 9. NoDesk
def scrape_nodesk():
    out = []
    try:
        f = feedparser.parse("https://nodesk.co/remote-jobs/index.xml")
        for e in f.entries:
            t = e.title
            if "intern" not in t.lower():
                continue
            out.append(Internship(
                t, "", "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "nodesk", [], e.get("published", ""), True))
    except Exception as e:
        print("nodesk", e)
    return out


# 10. JustRemote
def scrape_justremote():
    out = []
    try:
        f = feedparser.parse("https://justremote.co/remote-jobs/internships?format=rss")
        for e in f.entries:
            out.append(Internship(
                e.title, "", "Remote",
                _c(e.get("summary", ""))[:2000], e.link,
                "justremote", [], e.get("published", ""), True))
    except Exception as e:
        print("justremote", e)
    return out


SCRAPERS = [
    scrape_remotive, scrape_arbeitnow, scrape_hn_whoishiring,
    scrape_remoteok, scrape_jobicy, scrape_himalayas,
    scrape_weworkremotely, scrape_jobspresso, scrape_nodesk,
    scrape_justremote,
]


def run_all_scrapers():
    all_items = []
    for fn in SCRAPERS:
        try:
            its = fn()
            print(f"  {fn.__name__}: {len(its)}")
            all_items.extend(its)
        except Exception as e:
            print(f"  {fn.__name__}: FAILED {e}")
        time.sleep(0.6)
    seen, out = set(), []
    for it in all_items:
        if it.id in seen:
            continue
        seen.add(it.id)
        out.append(it)
    return out