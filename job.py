"""
Cron entrypoint. Run by GitHub Actions every 6 hours.
Scrapes sources, saves new internships, sends digests.
"""
import json
import os
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime

from db import init_db, get_subscribed_users
from emailer import run_digest_for

ROOT = os.path.dirname(os.path.abspath(__file__))
SCRAPE_TIMEOUT = 300  # seconds; the workflow itself allows 10 minutes


def run_scrapy() -> bool:
    """Scrape with Scrapy in a child process and save to PostgreSQL.

    A separate process because Twisted's reactor cannot be restarted: running
    Scrapy twice in one interpreter raises ReactorNotRestartable. The spiders'
    pipeline writes straight to the database; the summary comes back as JSON.
    """
    fd, summary_path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(ROOT, "run_spiders.py"),
             "--summary", summary_path],
            cwd=ROOT, timeout=SCRAPE_TIMEOUT)
        try:
            with open(summary_path) as f:
                s = json.load(f)
            print(f"[job] scraped {s['total_items']} items, {s['total_new']} new")
        except (OSError, ValueError):
            print("[job] no scrape summary was written")
        return proc.returncode == 0
    finally:
        if os.path.exists(summary_path):
            os.remove(summary_path)


def main():
    print(f"[job] start {datetime.utcnow().isoformat()}")
    init_db()

    failures = 0

    print("[job] scraping sources with Scrapy…")
    try:
        if not run_scrapy():
            failures += 1
            print("[job] scraping reported a problem (see log above)")
    except Exception:
        failures += 1
        print("[job] scraping failed:")
        traceback.print_exc()

    print("[job] sending digests…")
    total = 0
    try:
        for email in get_subscribed_users():
            try:
                r = run_digest_for(email)
                print(f"[job] {email}: {r}")
                total += r.get("sent", 0)
            except Exception:
                failures += 1
                print(f"[job] {email}: FAILED")
                traceback.print_exc()
    except Exception:
        failures += 1
        print("[job] digest loop failed:")
        traceback.print_exc()

    print(f"[job] done. total emails: {total}, problems: {failures}")
    # Non-zero exit makes the GitHub Actions run show red when something broke.
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())