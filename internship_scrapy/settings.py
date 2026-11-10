"""Scrapy settings. Everything here can be overridden with `-s NAME=value`
on the command line, or (for the few that matter in CI) by an env variable.
"""
import os


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


BOT_NAME = "internship_scrapy"
SPIDER_MODULES = ["internship_scrapy.spiders"]
NEWSPIDER_MODULE = "internship_scrapy.spiders"

# ── Politeness / compliance ──────────────────────────────────────────────
# Scrapy fetches /robots.txt first and skips anything it forbids.
# Set ROBOTSTXT_OBEY=0 in the environment only if you have a reason to.
ROBOTSTXT_OBEY = _env_bool("ROBOTSTXT_OBEY", True)
USER_AGENT = "Mozilla/5.0 (InternAgg/1.0)"
DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json,text/xml,application/rss+xml,*/*",
}

# ── Speed ────────────────────────────────────────────────────────────────
# Spiders run concurrently (one per source). Each source is a different
# domain, so a full run takes about as long as the slowest source.
CONCURRENT_REQUESTS = 16
CONCURRENT_REQUESTS_PER_DOMAIN = 4
AUTOTHROTTLE_ENABLED = True            # slows down automatically if a site is slow
AUTOTHROTTLE_START_DELAY = 0.5
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# ── Robustness ───────────────────────────────────────────────────────────
DOWNLOAD_TIMEOUT = 15
RETRY_ENABLED = True
RETRY_TIMES = 2                        # 2 retries on timeouts / 5xx / 429
CLOSESPIDER_TIMEOUT = 110              # hard stop per spider (seconds)
TELNETCONSOLE_ENABLED = False
STATS_DUMP = False                     # run_spiders.py prints its own compact summary

# ── Pipelines (lower number runs first) ──────────────────────────────────
ITEM_PIPELINES = {
    "internship_scrapy.pipelines.CleanPipeline": 100,
    "internship_scrapy.pipelines.IdPipeline": 200,
    "internship_scrapy.pipelines.DedupPipeline": 300,
    "internship_scrapy.pipelines.PostgresPipeline": 400,
}

# Set SAVE_TO_DB=0 to scrape without touching the database
# (handy with `scrapy crawl remotive -O out.json`).
SAVE_TO_DB = _env_bool("SAVE_TO_DB", True)

LOG_LEVEL = os.environ.get("LOG_LEVEL", "WARNING")   # LOG_LEVEL=INFO for details
FEED_EXPORT_ENCODING = "utf-8"
