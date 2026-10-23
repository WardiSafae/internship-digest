# Internship Aggregator

An automated internship discovery and delivery system. It scrapes 11 job sources every 6 hours, matches new postings against each subscriber's keywords, and sends personalized HTML email digests.

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

The full demo runs from `internships.ipynb`. Cells, top to bottom:

| Cell | What it does |
|------|--------------|
| 1 | Installs dependencies |
| 2 | Mounts Drive, loads secrets, creates a persistent `SECRET_KEY` |
| 3 | Database layer (auto-reconnect, PostgreSQL or SQLite backend) |
| 4 | Scrapers (9 global + 2 Moroccan) |
| 5 | Auth (bcrypt + signed session cookies) |
| 6 | Matcher (TF-IDF + title boost) |
| 7 | Emailer (SMTP + HTML digest) |
| 8 | FastAPI app |
| 9 | Launches uvicorn + ngrok tunnel |

Add these in the Colab Secrets panel (🔑) and enable "Notebook access" for each:

| Secret | Value |
|--------|-------|
| `DATABASE_URL` | Neon connection string |
| `SMTP_HOST` | `smtp-relay.brevo.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Brevo login |
| `SMTP_PASS` | Brevo SMTP key |
| `FROM_ADDR` | Verified sender address |
| `NGROK_TOKEN` | From https://dashboard.ngrok.com |
| `DRY_RUN` | `0` for real emails, `1` for testing |

After Cell 9 runs, the notebook prints a public ngrok URL that serves the web UI.

---

## File Structure

```
internship-digest/
├── db.py                 # Database layer (auto-reconnect, dual backend)
├── scrapers.py           # 11 active scrapers (9 global + 2 Moroccan)
├── matcher.py            # TF-IDF search + title boost
├── emailer.py            # HTML digest renderer + SMTP sender
├── job.py                # GitHub Actions entry point
├── web.py                # FastAPI web UI
├── matcher_web.py        # Lightweight matcher for the web app (no pandas)
├── requirements.txt      # Full deps (scrapers + matcher + web)
├── requirements-web.txt  # Slim deps (web only)
├── .github/
│   └── workflows/
│       └── digest.yml    # Cron schedule: every 6 hours
├── internships.ipynb     # Colab notebook (full demo)
└── README.md
```

---

## How Scraping Works

Eleven sources, three formats. The most structured option is used wherever a source allows it.

| Format | Sources | Approach |
|--------|---------|----------|
| JSON API (7) | Remotive, Arbeitnow, Hacker News (Algolia API), RemoteOK, Jobicy, Himalayas, Working Nomads | `requests.get(url).json()` |
| RSS feed (2) | Jobspresso, We Work Remotely | `feedparser` |
| HTML (2) | Rekrute, MarocAnnonces | `BeautifulSoup` + `lxml` with CSS selectors |

Every scraper returns `Internship` objects. The ID, `MD5(title|company|url)`, is the deduplication key.

A source that has no listing for entry-level roles is filtered locally with a keyword list (`intern`, `graduate`, `junior`, `entry`, `trainee`, `apprentice`).

### Resilience

1. **Per-request timeout** (8 to 12 seconds), so a hanging source cannot block the job.
2. **Per-source `try/except`**, so one failing source does not stop the others.
3. **Global 120-second budget** for the whole scraping run.

### Sample output

```
[scrapers] starting...
  OK scrape_remotive               17 items  (0.1s)
  OK scrape_arbeitnow              19 items  (0.3s)
  OK scrape_hn_whoishiring         30 items  (1.0s)
  OK scrape_jobspresso             10 items  (0.3s)
  OK scrape_remoteok               11 items  (0.5s)
  OK scrape_jobicy                  6 items  (0.1s)
  -- scrape_himalayas               0 items  (0.1s)
  OK scrape_weworkremotely          3 items  (0.8s)
  OK scrape_working_nomads          4 items  (0.6s)
  OK scrape_rekrute                 9 items  (0.9s)
  OK scrape_marocannonces          20 items  (0.5s)
[scrapers] done: 129 unique items in 8.6s
```

Source counts vary from run to run. Himalayas currently returns no entry-level results.

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
- **Trigger manually:** Actions → Internship Digest → Run workflow.
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
| `job.py` always exits with code 0 | A failed run still shows green in Actions | Count errors and exit non-zero |
| No retries on SMTP or HTTP errors | A failed send waits until the next run | Retry with backoff |
| No `robots.txt` check | Compliance is manual | Review each site's terms; prefer APIs |
| HTML scrapers depend on page structure | Break when a site is redesigned | Monitoring and alerts |
| `stagiaires_ma` scraper is defined but inactive | Timed out in testing | Re-test or remove |

---

## Technology Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Language | Python 3.11 | Scraping and data-science ecosystem |
| Web framework | FastAPI | Simple request parsing, async-capable |
| Server | Uvicorn | ASGI server |
| Database | PostgreSQL (Neon) | Network-accessible, persistent across runs |
| DB driver | psycopg2-binary | Standard Python PostgreSQL driver |
| HTTP | requests | Simple and well known |
| HTML parsing | BeautifulSoup + lxml | CSS-selector parsing |
| RSS | feedparser | Handles RSS/Atom quirks |
| Matching | scikit-learn (TF-IDF) | Standard information retrieval |
| Passwords | bcrypt | Purpose-built for password hashing |
| Signed tokens | itsdangerous | Signed sessions and links |
| Email | Brevo SMTP | Free tier with inbox delivery |
| Scheduling | GitHub Actions | Free scheduled runs |
| Tunnel | ngrok | Exposes Colab to the internet |
| Demo host | Google Colab | Free compute, Drive for persistence |

---

## Why Not Scrapy?

The project uses `requests` + BeautifulSoup instead of Scrapy, for these reasons:

1. **Little crawling is needed.** 9 of the 11 sources are JSON APIs or RSS feeds, so there is nothing to crawl. Only 2 sources need HTML parsing, and they are a handful of pages.
2. **Simplicity.** Each source is one function returning a list of `Internship` objects. Adding a source means writing one function, and a broken source can be debugged in isolation.
3. **Short-lived runs.** The job is a short cron script, and scraping is a small part of the project. Scrapy's Twisted reactor cannot be restarted in the same process, which complicates notebooks and servers that trigger scraping on demand.
4. **Adequate speed.** A full run takes about 10 seconds, so concurrency would add little.

What Scrapy would give that this code lacks: automatic retries, throttling, built-in `robots.txt` compliance, concurrency, and item pipelines. If the project grows to many HTML sources or needs deep crawling, Scrapy is the natural migration path: each scraper function becomes a Spider, the dataclass becomes an Item, and deduplication plus `save_internships()` become a pipeline.

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
- [ ] Migrate scrapers to Scrapy if the source count grows
- [ ] Playwright for JavaScript-heavy sites
- [ ] Public API (`/api/v1/internships`)
- [ ] Arabic tokenization for Arabic-only titles

---

## Contributing

This is a student project. To add a new source:

1. Write a `scrape_<name>()` function in `scrapers.py` that returns `List[Internship]`.
2. Add it to the `SCRAPERS` list.
3. Test it:
   ```bash
   python -c "from scrapers import scrape_<name>; print(len(scrape_<name>()))"
   ```
4. Commit.

---

## License

MIT License. See `LICENSE` for details.



**Safae Wardi**
[github.com/WardiSafae](https://github.com/WardiSafae)
University project, 2026
