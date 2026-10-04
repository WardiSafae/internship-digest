"""
Cron entrypoint. Run by GitHub Actions every 6 hours.
Scrapes sources, saves new internships, sends digests.
"""
import os
import sys
import traceback
from datetime import datetime

from db import init_db, save_internships, get_subscribed_users
from scrapers import run_all_scrapers
from emailer import run_digest_for


def main():
    print(f"[job] start {datetime.utcnow().isoformat()}")
    init_db()

    print("[job] scraping sources…")
    try:
        items = run_all_scrapers()
        added = save_internships(items)
        print(f"[job] scraped {len(items)} items, {added} new")
    except Exception:
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
                print(f"[job] {email}: FAILED")
                traceback.print_exc()
    except Exception:
        print("[job] digest loop failed:")
        traceback.print_exc()

    print(f"[job] done. total emails: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())