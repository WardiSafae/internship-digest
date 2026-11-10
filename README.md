# Internship Aggregator

An automated internship discovery and delivery system. It scrapes 11 job sources every 6 hours, matches new postings against each subscriber's keywords, and sends personalized HTML email digests.

> **Branch `scrapy-scraping`:** the scraping layer is rebuilt with **Scrapy** (spiders, items, item
> pipelines) instead of `requests` + BeautifulSoup. Everything else (database, matcher, e-mails, web UI)
> is unchanged. See [SCRAPY.md](SCRAPY.md) for the design, how to run it, and what differs from `main`.

**Live demo:** register at the ngrok URL printed when you run the notebook.
**Cost:** $0/month (free tiers only).

---

## What It Does

Scanning job boards by hand wastes hours. This system automates it:

1. **Scrapes** 11 sources: 9 global (Remotive, Arbeitnow, Hacker News "Who is hiring?", RemoteOK, Jobicy, Himalayas, We Work Remotely, Jobspresso, Working Nomads) and 2 Moroccan (Rekrute, MarocAnnonces).
2. **Deduplicates** by `MD5(title|company|url)`, so the same posting is stored once.
3. **Stores** everything in PostgreSQL (Neon free tier).
4. **Matches** each subscriber's keywords against postings with TF-IDF and a title boost.
5. **Emails** an HTML digest. Each internship is sent to a given user at most once.
6. **Runs automatically** every 6 hours on GitHub Actions, with no server to maintain.

---

## Architecture

```
┌─────────────────────┐     ┌───────────────────┐     ┌─────────────────────┐
│  Web UI (FastAPI)   │────►│    PostgreSQL     │◄────│  Cron Job (Actions) │
│  Register / Login   │     │  (Neon free tier) │     │  Every 6 hours      │
│  Dashboard / Search │     │                   │     │  Scrape → Match     │
│  Unsubscribe        │     │  internships      │     │  → Email            │
│                     │     │  users            │     │                     │
│  Runs on: Colab     │     │  sent             │     │  Runs on: GitHub    │
└─────────────────────┘     └───────────────────┘     └─────────────────────┘
```

Two independent processes (web UI and cron job) share one database. They never call each other directly.

---

## Quick Start

### Requirements

- Python 3.11+
- PostgreSQL (Neon free tier recommended)
- SMTP credentials (Brevo free tier recommended)
- ngrok token (free), only needed to expose the app from Colab

### Local setup

```bash
git clone https://github.com/WardiSafae/internship-digest.git
cd internship-digest
pip install -r requirements-web.txt
```

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
SECRET_KEY=<64-char hex string>
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASS=your-brevo-key
FROM_ADDR=your@email.com
APP_BASE_URL=http://localhost:8000
DRY_RUN=1
```

Start with `DRY_RUN=1` (emails are only printed). Set `DRY_RUN=0` when you want real emails.

Run the web app:

```bash
uvicorn web:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000.

### Run the cron job manually

```bash
python job.py
```

This scrapes all sources, saves new internships, and sends digests to all subscribed users.

---

## The Colab Notebook

`internship_aggregator.ipynb` only serves the **web interface**. It clones this repository, imports
`web.py` and exposes it through ngrok. Scraping and e-mailing are done by GitHub Actions, which writes
into the same PostgreSQL database the interface reads.

```
Colab (UI)  ──reads/writes──►  PostgreSQL (Neon)  ◄──writes──  GitHub Actions (Scrapy + digests)
```

| Cell | What it does |
|------|--------------|
| 1 | Installs the UI dependencies |
| 2 | Clones/updates the repository (branch set in `BRANCH`) |
| 3 | Reads the Colab secrets into environment variables |
| 4 | Shows what is in the shared database (offers per source, last scrape time, subscribers) |
| 5 | Starts uvicorn + ngrok and prints the public URL |

Add these in the Colab Secrets panel (🔑) and enable "Notebook access" for each:

| Secret | Value |
|--------|-------|
| `DATABASE_URL` | Same Neon connection string as GitHub Actions |
| `SECRET_KEY` | **Same value as the GitHub Actions secret**, otherwise unsubscribe links in e-mails are rejected |
| `NGROK_TOKEN` | From https://dashboard.ngrok.com |
| `GITHUB_TOKEN` | Optional, only if the repository is private |

The notebook forces `DRY_RUN=1`: the interface never sends e-mail.

---

## File Structure

```
internship-digest/
├── scrapy.cfg                 # Scrapy project marker
├── internship_scrapy/
│   ├── settings.py            # politeness, retries, concurrency, pipeline order
│   ├── items.py               # InternshipItem (one model for all sources)
│   ├── pipelines.py           # Clean -> Id -> Dedup -> Postgres
│   └── spiders/               # one spider per source (11)
├── run_spiders.py             # runs all spiders in one reactor, prints a summary
├── tests/                     # offline spider/pipeline tests (pytest)
├── db.py                      # Database layer (auto-reconnect, dual backend)
├── matcher.py                 # TF-IDF search + title boost
├── emailer.py                 # HTML digest renderer + SMTP sender
├── job.py                     # GitHub Actions entry point (scrape -> digests)
├── web.py                     # FastAPI web UI
├── requirements.txt           # Full deps (Scrapy + matcher + web)
├── requirements-web.txt       # Slim deps (web UI only)
├── .github/workflows/digest.yml   # Cron: every 6 hours
├── internship_aggregator.ipynb    # Colab notebook (UI only)
├── SCRAPY.md                  # Design notes for the Scrapy branch
└── README.md
```

---

## How Scraping Works

Scraping is done with **Scrapy**: one spider per source, all run concurrently in a single process by
`run_spiders.py`. The most structured format is used wherever a source offers it.

| Format | Sources | Approach in the spider |
|--------|---------|------------------------|
| JSON API (7) | Remotive, Arbeitnow, Hacker News (Algolia API), RemoteOK, Jobicy, Himalayas, Working Nomads | `response.json()` |
| RSS feed (2) | Jobspresso, We Work Remotely | XPath on the XML (`response.xpath("//item")`) |
| HTML (2) | Rekrute, MarocAnnonces | CSS selectors (`response.css(...)`) |

Spiders only **extract**. What happens next is done once, in item pipelines:
`CleanPipeline` (strip HTML, cap at 2000 chars, drop items without title/URL) →
`IdPipeline` (`MD5(title|company|url)`) → `DedupPipeline` (duplicates within a run) →
`PostgresPipeline` (`INSERT ... ON CONFLICT (id) DO NOTHING`).

Entry-level filtering is a keyword list (`intern`, `graduate`, `junior`, `entry`, `trainee`,
`apprentice`) applied inside the spiders whose source has no internship-only feed.

### Resilience

1. **Concurrency per source**: one spider per source, so a slow source does not delay the others.
2. **Retries** (2) on timeouts and 5xx/429, **AutoThrottle** slows down automatically if a site is slow.
3. **Timeouts**: 15 s per request and a hard 110 s limit per spider.
4. **`robots.txt` is obeyed** (`ROBOTSTXT_OBEY`); blocked requests are counted and reported.
5. **Failure isolation**: a failed source is logged and counted, the other spiders keep going.

### Run summary

`run_spiders.py` prints one line per source: items scraped, rows the source returned before filtering
(`seen`), new rows saved, rows already known, failed requests, robots.txt blocks and HTTP 4xx/5xx
answers. It exits with code 2 if not a single item came back.

---

## How Matching Works

### Stage 1: hard filters

- **Time window:** 24h / week / month / all
- **Remote only:** keep only postings flagged remote
- **Location:** word-boundary regex match against the location field or, as a fallback, the description

Word boundaries mean `us` does not match `Australia`.

### Stage 2: TF-IDF scoring

```python
score = 0.7 * cosine_similarity(query, full_text)
      + 0.3 * cosine_similarity(query, title)
```

This is classic lexical information retrieval (TF-IDF with unigrams and bigrams), not a semantic or embedding model. The title gets extra weight because a keyword in a title is a stronger signal than the same word in a long description. The 0.7 / 0.3 split is a heuristic choice and has not been formally tuned.

### Keyword expansion

`full-stack` also matches `full stack` and `fullstack`. The same applies to multi-word keywords such as `machine learning`.

### Example

Keyword `full-stack` matches "Software Engineering Intern (Full-Stack)" with a score above the default 0.12 threshold.

---

## How Email Delivery Works

Every 6 hours, the cron job:

1. Scrapes all sources.
2. Saves new internships to PostgreSQL.
3. For each subscribed user:
   - loads their keywords and preferences,
   - runs the matcher,
   - removes internships already sent to them,
   - renders an HTML digest with the top 10 new matches,
   - sends it through Brevo SMTP,
   - records the sent IDs.

### Deduplication guarantee

The `sent` table stores `(email, internship_id)` pairs. IDs are recorded only after a successful send, so a failed send is retried on the next run, and a posting is never re-sent to the same user. (In `DRY_RUN` mode nothing is recorded.)

### Failure isolation in `job.py`

Scraping, the user loop, and each individual user are wrapped separately in `try/except`. A failure in one stage or for one user does not stop the rest, and the full traceback is printed to the Actions logs.

### Example digest

```
Subject: 🎯 3 internship matches — 2026-10-22

Keywords: python, full-stack

[Software Engineering Intern (Full-Stack)]
Company · Munich · arbeitnow · match 0.15
[description snippet]
[View & apply →]

[Unsubscribe]
```

---

## Deployment

### The cron job

The GitHub Actions workflow is committed in `.github/workflows/digest.yml`.

- **Verify it runs:** open the repository's Actions tab.
- **Trigger manually:** Actions → Internship Digest → Run workflow. You can pick the branch to run
  (e.g. `scrapy-scraping`) and set `dry_run` to `1` to test without sending e-mails.
  Scheduled runs always use the repository's default branch.
- **Pause:** comment out the `schedule` block in the workflow file and commit.

GitHub scheduled workflows can be delayed under load, so "every 6 hours" is approximate.

### The web UI

The web UI currently runs from Colab through ngrok. For permanent hosting, deploy `web.py` to a service such as Render, Fly.io or Railway and set the environment variables below. Free tiers change often, so check each provider's current terms.

Start command:

```bash
uvicorn web:app --host 0.0.0.0 --port $PORT
```

### Environment variables

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | HMAC secret for sessions and unsubscribe tokens |
| `SMTP_HOST`, `SMTP_PORT` | SMTP server |
| `SMTP_USER`, `SMTP_PASS` | SMTP credentials |
| `FROM_ADDR` | Sender address (must be verified with the provider) |
| `APP_BASE_URL` | Public web UI URL (used in unsubscribe links) |
| `DRY_RUN` | `1` = print only, `0` = send real emails |

---

## Security

| Concern | Mitigation |
|---------|------------|
| Password storage | bcrypt with per-user salt |
| Session forging | Signed, time-limited cookies (`itsdangerous`, 30 days) |
| Unsubscribe forging | Separately signed tokens with a different salt (1 year) |
| SQL injection | Parameterized queries |
| Email hygiene | `List-Unsubscribe` header, `Precedence: bulk`, verified sender |
| Database transport | `sslmode=require` on the PostgreSQL connection |

### Known security gaps

- The "Scrape now" and "Email me matches now" routes are available to **any logged-in user**, not only an admin.
- HTML pages are built with f-strings and **do not escape** scraped content or user input, which exposes the app to cross-site scripting.
- Session cookies are not marked `Secure`.
- No rate limiting on login or registration.

These should be fixed before any real production use.

---

## Current Limitations

| Limitation | Impact | Planned fix |
|------------|--------|-------------|
| Web UI runs on Colab | No UI when the notebook is closed | Deploy to a hosting service |
| No email verification | Anyone can register any address | Verification link flow |
| No password reset | Forgotten password means lockout | Token-based reset |
| ~130 internships per run | Limited coverage | Add a job-aggregator API (e.g. Adzuna) |
| Some Moroccan sites block scripts | Emploi.ma, ANAPEC unavailable | Headless browser (Playwright) |
| Lexical TF-IDF matching | Misses synonyms | Sentence embeddings |
| Entry-level filter is a substring match | "intern" also matches "internal"; French terms (`stage`, `stagiaire`) are not in the list | Word-boundary matching and French keywords |
| No retry on SMTP errors | A failed send waits until the next run (HTTP requests are retried by Scrapy) | Retry with backoff |
| `robots.txt` is obeyed, terms of service are not checked | A source may be blocked by robots.txt | Review each site's terms; prefer APIs |
| HTML scrapers depend on page structure | Break when a site is redesigned | Monitoring and alerts |
| `stagiaires_ma` was not ported | Timed out in testing on `main` | Re-test, then add a spider |

---

## Technology Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Language | Python 3.11 | Scraping and data-science ecosystem |
| Web framework | FastAPI | Simple request parsing, async-capable |
| Server | Uvicorn | ASGI server |
| Database | PostgreSQL (Neon) | Network-accessible, persistent across runs |
| DB driver | psycopg2-binary | Standard Python PostgreSQL driver |
| Scraping | Scrapy | Spiders, concurrency, retries, robots.txt, item pipelines |
| Parsing | parsel (CSS/XPath, bundled with Scrapy) | One selector API for HTML, XML and JSON |
| Matching | scikit-learn (TF-IDF) | Standard information retrieval |
| Passwords | bcrypt | Purpose-built for password hashing |
| Signed tokens | itsdangerous | Signed sessions and links |
| Email | Brevo SMTP | Free tier with inbox delivery |
| Scheduling | GitHub Actions | Free scheduled runs |
| Tunnel | ngrok | Exposes Colab to the internet |
| Demo host | Google Colab | Free compute, Drive for persistence |

---

## Why Scrapy (this branch) and not `requests` + BeautifulSoup (`main`)

`main` keeps the simple version; this branch exists to compare. Scrapy adds what the hand-written
version lacked: concurrency, retries, throttling, `robots.txt` compliance, and a standard place
(pipelines) for cleaning, deduplication and storage. The cost is a framework to learn, more files,
and the Twisted reactor, which cannot be restarted: that is why `job.py` runs the spiders in a child
process (`run_spiders.py`) instead of calling Scrapy from inside its own process.

For 11 sources, most of them JSON APIs, the speed difference is small (a full run was already about
10 seconds). The practical gains are the built-in politeness and the clearer separation of
*extracting* (spiders) from *processing and storing* (pipelines). Details and the list of behavioural
differences are in [SCRAPY.md](SCRAPY.md).

---

## Roadmap

**Short term**
- [ ] Deploy the web UI to permanent hosting
- [ ] Escape all HTML output and restrict admin routes
- [ ] Email verification on registration
- [ ] Password reset flow
- [ ] Non-zero exit code on failure in `job.py`

**Medium term**
- [ ] Add a job-aggregator API for more volume
- [ ] Add more Moroccan sources
- [ ] Word-boundary and French keywords in the entry-level filter
- [ ] Replace TF-IDF with sentence embeddings
- [ ] Per-source health monitoring with alerts

**Long term**
- [x] Migrate scrapers to Scrapy (branch `scrapy-scraping`)
- [ ] Playwright for JavaScript-heavy sites
- [ ] Public API (`/api/v1/internships`)
- [ ] Arabic tokenization for Arabic-only titles

---

## Contributing

This is a student project. To add a new source:

1. Create `internship_scrapy/spiders/<name>.py` with a spider that subclasses `InternshipSpider`,
   sets `name` and `start_urls`, and yields `self.make_item(title=..., url=..., ...)` from `parse()`.
2. Test it offline: add a small fixture to `tests/fixtures.py` and a test to `tests/test_spiders.py`, then `pytest -q`.
3. Try it without touching the database:
   ```bash
   SAVE_TO_DB=0 scrapy crawl <name> -O out.json
   ```
4. Commit. `run_spiders.py` discovers the new spider automatically.

---

## License

MIT License. See `LICENSE` for details.



**Safae Wardi**
[github.com/WardiSafae](https://github.com/WardiSafae)
University project, 2026
