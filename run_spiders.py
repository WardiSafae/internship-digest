"""Run every spider concurrently in ONE Twisted reactor, then print a summary.

    python run_spiders.py                      # all spiders
    python run_spiders.py remotive rekrute     # only these
    python run_spiders.py --summary out.json   # also write the summary as JSON

job.py runs this script in a separate process: Twisted's reactor cannot be
restarted, so Scrapy must never be started twice inside one Python process.

Exit code: 0 = ran fine, 2 = not a single item came back (network down?
every source blocked?), 1 = crash.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SCRAPY_SETTINGS_MODULE", "internship_scrapy.settings")

from scrapy.crawler import CrawlerProcess  # noqa: E402
from scrapy.utils.project import get_project_settings  # noqa: E402


def _errors(stats, prefix):
    return sum(v for k, v in stats.items()
               if k.startswith(prefix) and k[len(prefix):][:1] in "45")


def summarize(crawlers, elapsed):
    rows = []
    for crawler in crawlers:
        st = crawler.stats.get_stats()
        rows.append({
            "spider": crawler.spidercls.name,
            "items": st.get("item_scraped_count", 0),
            "dropped": st.get("item_dropped_count", 0),
            "rows_seen": st.get("source/rows_seen", 0),
            "new_in_db": st.get("db/inserted", 0),
            "already_known": st.get("db/already_known", 0),
            "failed_requests": st.get("source/failed", 0),
            "robots_blocked": st.get("robotstxt/forbidden", 0),
            # 4xx/5xx answers, not counting the harmless robots.txt 404
            "http_errors": _errors(st, "downloader/response_status_count/")
                           - _errors(st, "robotstxt/response_status_count/"),
            "finish_reason": st.get("finish_reason", "?"),
        })
    rows.sort(key=lambda r: r["spider"])
    return {
        "elapsed_s": round(elapsed, 1),
        "total_items": sum(r["items"] for r in rows),
        "total_new": sum(r["new_in_db"] for r in rows),
        "spiders": rows,
    }


def print_table(s):
    print("\n[scrapy] summary")
    print(f"  {'spider':16s} {'items':>5s} {'seen':>5s} {'new':>4s} {'known':>5s} "
          f"{'fail':>4s} {'robots':>6s} {'http4/5xx':>9s}  reason")
    for r in s["spiders"]:
        mark = "OK" if r["items"] else "--"
        print(f"{mark} {r['spider']:16s} {r['items']:5d} {r['rows_seen']:5d} "
              f"{r['new_in_db']:4d} {r['already_known']:5d} {r['failed_requests']:4d} "
              f"{r['robots_blocked']:6d} {r['http_errors']:9d}  {r['finish_reason']}")
    print(f"[scrapy] {s['total_items']} items, {s['total_new']} new, in {s['elapsed_s']}s")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("spiders", nargs="*", help="spider names (default: all)")
    ap.add_argument("--summary", help="write the summary to this JSON file")
    args = ap.parse_args(argv)

    process = CrawlerProcess(get_project_settings())
    names = args.spiders or sorted(process.spider_loader.list())
    # Keep our own references: CrawlerProcess forgets finished crawlers.
    crawlers = [process.create_crawler(name) for name in names]
    for crawler in crawlers:
        process.crawl(crawler)

    t0 = time.time()
    process.start()          # blocks until every spider has finished
    summary = summarize(crawlers, time.time() - t0)

    print_table(summary)
    if args.summary:
        with open(args.summary, "w") as f:
            json.dump(summary, f, indent=2)
    return 2 if summary["total_items"] == 0 else 0


if __name__ == "__main__":
    sys.exit(main())
