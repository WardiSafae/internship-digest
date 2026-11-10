# Scrapy branch (`scrapy-scraping`)

The scraping layer of `main` (`scrapers.py`: `requests` + BeautifulSoup + `feedparser`) is replaced by a
**Scrapy** project. Database, matcher, e-mails and web UI are unchanged.

```
                     ┌──────────────────────── GitHub Actions (every 6 h) ───────────────────────┐
                     │ job.py ──► run_spiders.py (child process, one Twisted reactor)            │
                     │              11 spiders ─► Clean ─► Id ─► Dedup ─► Postgres pipeline ─┐   │
                     │ job.py ──► digests (matcher + e-mail) ◄────────────────────────────────┼─┐ │
                     └────────────────────────────────────────────────────────────────────────┼─┼─┘
                                                                                              ▼ ▼
 Colab notebook ── web.py (register / search / subscribe) ───────────────►  PostgreSQL (Neon): internships, users, sent
```

Users interact with Colab. Data is produced by GitHub. Both use the same database.

## Layout

| Path | Role |
|------|------|
| `internship_scrapy/spiders/*.py` | One spider per source. They only **extract** fields. |
| `internship_scrapy/items.py` | `InternshipItem`: same columns as the `internships` table. |
| `internship_scrapy/pipelines.py` | `CleanPipeline` → `IdPipeline` → `DedupPipeline` → `PostgresPipeline`. |
| `internship_scrapy/settings.py` | Robots.txt, retries, AutoThrottle, timeouts, pipeline order. |
| `run_spiders.py` | Runs all spiders concurrently, prints a summary, exit code 2 if nothing came back. |
| `job.py` | Calls `run_spiders.py` in a **child process**, then sends the digests. |
| `db.py` | Gains `insert_internship()` (`ON CONFLICT (id) DO NOTHING`). |
| `tests/` | Offline tests with fixtures; one optional test against a real PostgreSQL. |

`scrapers.py` is removed on this branch, and `web.py` no longer imports it.

## Run it

```bash
pip install -r requirements.txt

# one spider, no database, result in a file
SAVE_TO_DB=0 scrapy crawl remotive -O out.json

# all spiders -> PostgreSQL (needs DATABASE_URL)
python run_spiders.py
python run_spiders.py remotive rekrute        # only some
LOG_LEVEL=INFO python run_spiders.py          # more detail

# the whole cron job (scrape + digests); DRY_RUN=1 prints instead of sending
DRY_RUN=1 python job.py

# tests
pip install pytest && pytest -q
TEST_DATABASE_URL=postgresql://... pytest -q tests/test_postgres_pipeline.py
```

**On GitHub:** Actions → *Internship Digest* → *Run workflow* → choose the branch `scrapy-scraping`
and set `dry_run` = `1` for a first test. Scheduled (cron) runs only ever use the default branch, so
the Scrapy version runs on a schedule only once it is merged into `main`.

**In Colab:** `internship_aggregator.ipynb` clones the branch set in its `BRANCH` variable and serves
`web.py`. Its `SECRET_KEY` secret must equal the GitHub secret, because the unsubscribe links in the
e-mails are signed with it.

## Same output as `main`

The `id` is still `MD5(title|company|url)` (lowercased) and the field mapping of every source was ported
one to one, so both branches write to the same table without creating duplicates. This was checked by
running the old scrapers and the new spiders on the same fixture for each of the 11 sources and comparing
id, title, company, URL, location, source, remote flag and date: identical, except for the two points below.

## What differs from `main` (on purpose)

| Change | Why | Effect |
|--------|-----|--------|
| `robots.txt` is obeyed | Compliance; Scrapy does it natively | A source whose robots.txt forbids the URL returns nothing. It shows in the summary (`robots` column) and the log. Set `ROBOTSTXT_OBEY=0` to turn it off. |
| MarocAnnonces URLs are absolute | The site lists hrefs like `categorie/309/...` with no leading slash; `main` stored them as-is, so the "View & apply" links were relative and broken | New rows have a different `id` from the old rows of this source (the URL is part of the id). See the cleanup SQL below. |
| Rekrute: pages 1 to 3 are all fetched | In `main`, the loop stopped after the first page that returned results, so only page 1 was used | Up to 3x more Rekrute offers. Change with `scrapy crawl rekrute -a pages=N`. |
| Descriptions are stored as plain text | They were raw HTML and are shown unescaped in the UI and e-mails | Cleaner e-mail previews, less noise in TF-IDF, and no markup injected from scraped content. Old rows keep their HTML. |
| Items without title or URL are dropped | They cannot be deduplicated or opened | Rare. |
| `job.py` exits with code 1 if scraping or any digest failed | A broken run used to show green in Actions | You will get failure notifications from GitHub. |
| All sources run concurrently | Scrapy engine | The run takes about as long as the slowest source. |
| `stagiaires_ma` not ported | Inactive on `main` (timed out) | Add a spider if the site is reachable again. |

Not changed, to keep the comparison fair: the entry-level keyword filter (still a substring match, so
`intern` also matches `internal`, and French terms such as `stage` are not in the list).

### One-off cleanup after the first run on this branch

```sql
-- remove the old MarocAnnonces rows that have relative (broken) URLs;
-- the spider re-creates them with absolute URLs on the next run
DELETE FROM internships WHERE source = 'marocannonces' AND url NOT LIKE 'http%';
```

## What was and was not tested

Tested here, offline: all 11 spiders against fixtures (19 unit tests); old-versus-new comparison on every
source; a full crawl through the real Scrapy engine against a local HTTP server, writing to a real
PostgreSQL (15 rows inserted, a second run inserts nothing new, robots.txt blocking is reported,
a run with every request failing exits with code 2 and `job.py` still sends the digests and exits 1);
the web UI searching data written by the pipeline; the notebook's server start/restart logic.

**Not tested: the live websites.** The sandbox could not reach them, and the fixtures are hand-written
from your notes and diagnostics. Before trusting the branch, run it once for real (Actions with
`dry_run=1`, or `python run_spiders.py` locally) and read the summary table: a source with `seen = 0`
and `fail > 0` is unreachable, `robots > 0` is blocked by robots.txt, `seen > 0` and `items = 0` means
its selectors or filter matched nothing. The Rekrute and MarocAnnonces selectors are the most likely to
need a tweak if a site changed its HTML.

## Design notes

- **Why a child process?** Twisted's reactor cannot be restarted. Running Scrapy twice in one Python
  process (for example from a button in the web app) raises `ReactorNotRestartable`. `job.py` therefore
  starts `run_spiders.py` as a separate process each time.
- **Why a pipeline writes to the database?** Spiders stay pure (URL in, items out) and are easy to test;
  storage is in one place. The pipeline uses blocking `psycopg2` calls inside the reactor, which is fine
  for a few hundred rows; for much larger crawls use `twisted.enterprise.adbapi` or a thread.
- **Pinned version:** `Scrapy==2.19.0`, the version the tests were run with. The spiders use
  `async def start()` and the pipelines use the argument-less `open_spider(self)` signatures of recent
  Scrapy releases, so older versions (below 2.13) will not work.
