"""Item pipelines: what happens to every item after a spider yields it.

    spider -> CleanPipeline -> IdPipeline -> DedupPipeline -> PostgresPipeline

Spiders only extract; cleaning, identity, deduplication and storage live
here, once, instead of being repeated in each scraper.
"""
import hashlib
from datetime import datetime

from scrapy.exceptions import DropItem, NotConfigured
from w3lib.html import remove_tags, replace_entities

from internship_scrapy.spiders.base import clean

MAX_DESCRIPTION = 2000


class CleanPipeline:
    """Drop unusable items and normalise the fields."""

    def process_item(self, item):
        if not item.get("title") or not item.get("url"):
            raise DropItem("missing title or url")

        # HTML -> plain text, whitespace collapsed, capped at 2000 chars.
        # (Descriptions are shown unescaped in the web UI and e-mails, and
        #  tag names such as "li"/"strong" only add noise to TF-IDF.)
        desc = replace_entities(remove_tags(item.get("description") or ""))
        item["description"] = clean(desc)[:MAX_DESCRIPTION]

        for f in ("company", "location", "posted_at"):
            item[f] = item.get(f) or ""
        item["tags"] = list(item.get("tags") or [])
        item["remote"] = bool(item.get("remote"))
        return item


class IdPipeline:
    """Deterministic id = MD5(title|company|url), lowercased.

    Identical to the id used by the requests-based scrapers on `main`, so
    both branches de-duplicate against the same `internships` table.
    """

    def process_item(self, item):
        key = f"{item['title']}|{item['company']}|{item['url']}".lower()
        item["id"] = hashlib.md5(key.encode()).hexdigest()
        return item


class DedupPipeline:
    """Drop duplicates inside one run (the DB handles duplicates across runs)."""

    def __init__(self):
        self.seen = set()

    def process_item(self, item):
        if item["id"] in self.seen:
            raise DropItem("duplicate in this run")
        self.seen.add(item["id"])
        return item


class PostgresPipeline:
    """INSERT ... ON CONFLICT (id) DO NOTHING, committed in batches.

    Uses the project's own `db` module (same connection logic and schema as
    the web app and the digest job). Blocking psycopg2 calls are fine at
    this volume (~100-300 rows); for much larger crawls use
    twisted.enterprise.adbapi or defer to a thread.
    """
    BATCH = 50

    def __init__(self, crawler):
        self.crawler = crawler
        self.pending = 0

    @classmethod
    def from_crawler(cls, crawler):
        if not crawler.settings.getbool("SAVE_TO_DB"):
            raise NotConfigured("SAVE_TO_DB is off")
        return cls(crawler)

    def open_spider(self):
        import db  # imported here so `scrapy list` works without DATABASE_URL
        self.db = db
        db.init_db()

    def process_item(self, item):
        stats = self.crawler.stats
        scraped_at = datetime.utcnow().isoformat()
        with self.db._DB_LOCK:
            cur = self.db.get_conn().cursor()
            inserted = self.db.insert_internship(cur, dict(item), scraped_at)
        stats.inc_value("db/inserted" if inserted else "db/already_known")
        self.pending += 1
        if self.pending >= self.BATCH:
            self._commit()
        return item

    def close_spider(self):
        self._commit()

    def _commit(self):
        with self.db._DB_LOCK:
            self.db.get_conn().commit()
        self.pending = 0
