import re, time, hashlib, requests, feedparser
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List

HEADERS = {
    "User-Agent": "Mozilla/5.0 (InternAgg/1.0)",
    "Accept": "application/json,text/xml,application/rss+xml,*/*",
}
ENTRY_TERMS = ("intern", "graduate", "junior", "entry", "trainee", "apprentice")

def _c(t): return re.sub(r"\s+", " ", (t or "")).strip()
def _is_entry_level(text):
    t = (text or "").lower()
    return any(term in t for term in ENTRY_TERMS)

def _fetch_feed(url, timeout=8):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return feedparser.parse(r.content) if r.status_code == 200 else None
    except Exception:
        return None

@dataclass
class Internship:
    title: str = ""; company: str = ""; location: str = ""
    description: str = ""; url: str = ""; source: str = ""
    tags: List[str] = field(default_factory=list)
    posted_at: str = ""; remote: bool = False
    id: str = ""
    def __post_init__(self):
        if not self.id:
            k = f"{self.title}|{self.company}|{self.url}".lower()
            self.id = hashlib.md5(k.encode()).hexdigest()

# ═══════════════════════════════════════════════════════════
# GLOBAL SOURCES (9 working)
# ═══════════════════════════════════════════════════════════

def scrape_remotive():
    out = []
    try:
        r = requests.get("https://remotive.com/api/remote-jobs",
                         params={"search": "intern"}, headers=HEADERS, timeout=10)
        for j in r.json().get("jobs", []):
            out.append(Internship(
                j.get("title", ""), j.get("company_name", ""),
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
            if not _is_entry_level(t): continue
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
            if not _is_entry_level(txt): continue
            plain = _c(BeautifulSoup(txt, "lxml").get_text())
            out.append(Internship(plain[:120], "", "", plain[:2000],
                f"https://news.ycombinator.com/item?id={c['id']}", "hn_whoishiring"))
    except Exception as e:
        print(f"  [hn] {type(e).__name__}")
    return out

def scrape_jobspresso():
    out = []
    f = _fetch_feed("https://jobspresso.co/?feed=job_feed&job_categories=internship")
    if not f: return out
    for e in f.entries:
        out.append(Internship(e.title, "", "Remote",
            _c(e.get("summary", ""))[:2000], e.link, "jobspresso",
            [], e.get("published", ""), True))
    return out

def scrape_remoteok():
    out = []
    try:
        r = requests.get("https://remoteok.com/api", headers=HEADERS, timeout=8)
        rows = r.json()[1:] if isinstance(r.json(), list) else []
        for j in rows:
            title = j.get("position", "")
            tags = [t.lower() for t in (j.get("tags") or [])]
            if not _is_entry_level(title + " " + " ".join(tags)): continue
            out.append(Internship(title, j.get("company", ""),
                j.get("location", "Remote"), _c(j.get("description", ""))[:2000],
                j.get("url", ""), "remoteok", j.get("tags", []),
                str(j.get("date", "")), True))
    except Exception as e:
        print(f"  [remoteok] {type(e).__name__}")
    return out

def scrape_jobicy():
    out = []
    try:
        r = requests.get("https://jobicy.com/api/v2/remote-jobs",
                         params={"count": 100}, headers=HEADERS, timeout=8)
        for j in r.json().get("jobs", []):
            t = j.get("jobTitle", "")
            if not _is_entry_level(t): continue
            out.append(Internship(t, j.get("companyName", ""),
                j.get("jobGeo", "Remote"), _c(j.get("jobExcerpt", ""))[:2000],
                j.get("url", ""), "jobicy", [], j.get("pubDate", ""), True))
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
            t = j.get("title") or j.get("jobTitle", "")
            if not _is_entry_level(t): continue
            out.append(Internship(t, j.get("companyName") or j.get("company", ""),
                j.get("location") or j.get("jobGeo", "Remote"),
                _c(j.get("description", ""))[:2000],
                j.get("applicationLink") or j.get("url", ""),
                "himalayas", j.get("categories", []) or [],
                str(j.get("pubDate", "")), True))
    except Exception as e:
        print(f"  [himalayas] {type(e).__name__}")
    return out

def scrape_weworkremotely():
    out = []
    for url in ["https://weworkremotely.com/remote-jobs.rss",
                "https://weworkremotely.com/categories/remote-jobs.rss"]:
        f = _fetch_feed(url)
        if not f or not f.entries: continue
        for e in f.entries:
            t = e.title
            if not _is_entry_level(t): continue
            out.append(Internship(t, e.get("author", ""), "Remote",
                _c(e.get("summary", ""))[:2000], e.link, "weworkremotely",
                [], e.get("published", ""), True))
        if out: break
    return out

def scrape_working_nomads():
    out = []
    try:
        r = requests.get("https://www.workingnomads.com/api/exposed_jobs/",
                         headers=HEADERS, timeout=8)
        for j in r.json():
            t = j.get("title", "")
            if not _is_entry_level(t): continue
            out.append(Internship(t, j.get("company_name", ""),
                j.get("location", "Remote"), _c(j.get("description", ""))[:2000],
                j.get("url", ""), "working_nomads",
                j.get("tags", []) or [], j.get("pub_date", ""), True))
    except Exception as e:
        print(f"  [working_nomads] {type(e).__name__}")
    return out

# ═══════════════════════════════════════════════════════════
# MOROCCAN SOURCES
# ═══════════════════════════════════════════════════════════

MOROCCO_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MOROCCAN_CITIES = [
    "casablanca", "rabat", "marrakech", "fès", "fes", "tanger", "tangier",
    "agadir", "meknès", "meknes", "oujda", "kénitra", "kenitra", "tétouan",
    "tetouan", "safi", "el jadida", "beni mellal", "nador", "mohammedia",
    "asilah", "assilah", "salé", "sale", "berrechid", "khouribga",
    "settat", "essaouira", "laâyoune", "dakhla", "errachidia",
    "taza", "al hoceima", "ifrane", "ouarzazate", "taroudant",
    "morocco", "maroc",
]


def _morocco_get(url, timeout=12):
    try:
        r = requests.get(url, headers=MOROCCO_HEADERS, timeout=timeout)
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"    fetch {url[:60]} → {type(e).__name__}")
        return None


def scrape_rekrute():
    """
    Rekrute.com — Morocco's largest job board.
    Offer structure: <li class='post-id'> containing <h2><a>Title</a></h2>
    plus a description block. Skip nav links and buttons.
    """
    out = []
    for page in range(1, 4):
        url = f"https://www.rekrute.com/offres.html?s=1&p={page}&o=1"
        r = _morocco_get(url)
        if not r:
            continue
        soup = BeautifulSoup(r.text, "lxml")

        # Rekrute uses <li class="post-id"> for each offer in the list
        items_found = soup.select("li.post-id")
        if not items_found:
            # Fallback: any <li> that contains a <h2><a> child
            items_found = [li for li in soup.find_all("li")
                           if li.find("h2") and li.find("h2").find("a")]

        for li in items_found:
            # The real title is in the <h2><a> of the li
            a = li.select_one("h2 a")
            if not a:
                continue

            title = _c(a.get_text())
            # Guard against nav items / buttons like "Lancer 4K"
            if not title or len(title) < 8:
                continue
            # Skip obvious non-jobs
            if title.lower() in {"lancer 4k", "postuler", "voir l'offre",
                                  "voir plus", "en savoir plus"}:
                continue

            href = a.get("href", "")
            if href.startswith("/"):
                href = "https://www.rekrute.com" + href

            # Description comes from the .info block inside the li
            info_el = li.select_one(".info, .desc, .job-description")
            description = _c(info_el.get_text())[:500] if info_el else ""

            # Location is often written as "| Casablanca (Maroc)" inside
            # a <em> or <span> tag, or in the description text.
            location = "Morocco"
            loc_el = li.select_one(".location, em, .city")
            if loc_el:
                loc_text = _c(loc_el.get_text()).lower()
                for city in MOROCCAN_CITIES:
                    if city in loc_text:
                        location = city.title()
                        break
            # Fallback: search description for a city name
            if location == "Morocco" and description:
                for city in MOROCCAN_CITIES:
                    if city in description.lower():
                        location = city.title()
                        break

            # Company is often not in the list view (only on the detail page).
            # Leave blank — the digest shows company='—' if missing.
            company = ""

            # Tags from the info block
            tags = ["morocco"]
            li_text = li.get_text(" ").lower()
            if "stage" in li_text:   tags.append("stage")
            if "junior" in li_text:  tags.append("junior")
            if "cdi" in li_text:     tags.append("cdi")
            if "confirmé" in li_text: tags.append("senior")

            # Keep only entry-level roles (junior/stage/intern) for the digest.
            # The Rekrute URL filter (s=1) already restricts to junior-level,
            # but we double-check the title for clarity.
            if not _is_entry_level(title):
                # Rekrute's `s=1` param includes some mid-level jobs; skip if
                # the title clearly indicates seniority.
                if any(k in title.lower() for k in ("senior", "expert", "confirmé", "lead")):
                    continue

            out.append(Internship(
                title=title,
                company=company,
                location=location,
                description=description,
                url=href,
                source="rekrute",
                tags=tags,
                posted_at="",
                remote=False,
            ))

        if out:
            break  # got results, no need to keep looping

    return out


def scrape_marocannonces():
    """
    MarocAnnonces.com — classifieds with an Emploi section.
    Job links follow the pattern: /categorie/309/Offres-emploi/annonce/{id}/{slug}.html
    """
    out = []
    for url in [
        "https://www.marocannonces.com/maroc/emploi.html",
        "https://www.marocannonces.com/categorie/309/Emploi/Offres-emploi.html",
    ]:
        r = _morocco_get(url)
        if not r:
            continue

        soup = BeautifulSoup(r.text, "lxml")

        # Match the specific annonce URL pattern
        links = soup.select("a[href*='/annonce/']")
        # Filter out nav/menu links
        links = [a for a in links if a.get_text(strip=True) and len(a.get_text(strip=True)) > 5]
        if not links:
            continue

        for a in links[:60]:
            title = _c(a.get_text())
            href = a["href"]
            if href.startswith("/"):
                href = "https://www.marocannonces.com" + href

            # The title often concatenates title + city: "Chargé(e) de Paie /BerrechidBerrechid"
            # Try to extract the city from the end
            location = "Morocco"
            for city in MOROCCAN_CITIES:
                if city in title.lower():
                    location = city.title()
                    break

            # Extract company if the link's parent has one
            company = ""
            parent = a.find_parent(["div", "li", "article"])
            if parent:
                comp = parent.select_one(".company, .advertiser, b")
                if comp:
                    company = _c(comp.get_text())

            out.append(Internship(
                title=title,
                company=company,
                location=location,
                description="",
                url=href,
                source="marocannonces",
                tags=["morocco"],
                posted_at="",
                remote=False,
            ))

        if out:
            break

    return out


def scrape_stagiaires_ma():
    """
    Stagiaires.ma — Morocco-specific internship board.
    Root page has a listing; no /offres-de-stage sub-path.
    """
    out = []
    r = _morocco_get("https://www.stagiaires.ma/")
    if not r:
        return out
    soup = BeautifulSoup(r.text, "lxml")

    # Look for stage/internship links in the landing page
    for a in soup.select("a[href*='/stage'], a[href*='/offre'], a[href*='/stages']")[:60]:
        title = _c(a.get_text())
        if not title or len(title) < 5:
            continue
        if not (_is_entry_level(title) or "stage" in title.lower()):
            continue
        href = a["href"]
        if href.startswith("/"):
            href = "https://www.stagiaires.ma" + href
        out.append(Internship(
            title=title, company="", location="Morocco",
            description="", url=href,
            source="stagiaires_ma", tags=["morocco", "stage"],
            posted_at="", remote=False,
        ))

    return out

# ═══════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════

SCRAPERS = [
    # Global
    scrape_remotive, scrape_arbeitnow, scrape_hn_whoishiring,
    scrape_jobspresso, scrape_remoteok, scrape_jobicy,
    scrape_himalayas, scrape_weworkremotely, scrape_working_nomads,
    # Moroccan
    scrape_rekrute, scrape_marocannonces,
]

def save_internships(items):
    con = init_db()
    n = 0
    with _DB_LOCK:
        cur = con.cursor()
        for it in items:
            cur.execute(_q("SELECT 1 FROM internships WHERE id=?"), (it.id,))
            if cur.fetchone(): continue
            cur.execute(_q("""INSERT INTO internships
                (id,title,company,location,description,url,source,tags,
                 posted_at,remote,scraped_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)"""),
                (it.id, it.title, it.company, it.location, it.description,
                 it.url, it.source, json.dumps(it.tags), it.posted_at,
                 int(it.remote), datetime.utcnow().isoformat()))
            n += 1
        con.commit()
    return n

def run_all_scrapers(global_timeout=120):
    all_items = []
    print("[scrapers] starting...")
    start = time.time()
    for fn in SCRAPERS:
        if time.time() - start > global_timeout:
            print(f"[scrapers] budget exceeded ({global_timeout}s), stopping")
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
        if it.id in seen: continue
        seen.add(it.id); out.append(it)

    print(f"[scrapers] done: {len(out)} unique items in {time.time()-start:.1f}s")
    return out

# Seed if DB is empty
con = init_db()
with _DB_LOCK:
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM internships")
    count = cur.fetchone()[0]

if count == 0:
    print("Seeding DB...")
    save_internships(run_all_scrapers())
    print("Done.")
else:
    print(f"DB already has {count} internships.")
