"""Helpers and the base class shared by all spiders."""
import re

import scrapy

from internship_scrapy.items import InternshipItem

ENTRY_TERMS = ("intern", "graduate", "junior", "entry", "trainee", "apprentice")

MOROCCAN_CITIES = [
    "casablanca", "rabat", "marrakech", "fès", "fes", "tanger", "tangier",
    "agadir", "meknès", "meknes", "oujda", "kénitra", "kenitra", "tétouan",
    "tetouan", "safi", "el jadida", "beni mellal", "nador", "mohammedia",
    "asilah", "assilah", "salé", "sale", "berrechid", "khouribga",
    "settat", "essaouira", "laâyoune", "dakhla", "errachidia",
    "taza", "al hoceima", "ifrane", "ouarzazate", "taroudant",
    "morocco", "maroc",
]

# Moroccan sites answered the browser-like headers during testing,
# so those spiders override the defaults with these.
BROWSER_SETTINGS = {
    "USER_AGENT": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36"),
    "DEFAULT_REQUEST_HEADERS": {
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    },
}


def clean(text) -> str:
    """Collapse all whitespace runs to a single space."""
    return re.sub(r"\s+", " ", (text or "")).strip()


def is_entry_level(text) -> bool:
    """Substring match on intern/graduate/junior/... (same rule as the
    requests-based version, so both branches select the same offers)."""
    t = (text or "").lower()
    return any(term in t for term in ENTRY_TERMS)


def find_city(text: str, default: str = "Morocco") -> str:
    low = (text or "").lower()
    for city in MOROCCAN_CITIES:
        if city in low:
            return city.title()
    return default


class InternshipSpider(scrapy.Spider):
    """Base class: request/errback plumbing + a factory for items.

    Subclasses set `name` and `start_urls`, then implement `parse()`.
    """
    start_urls: list = []

    async def start(self):
        for url in self.start_urls:
            yield self.request(url, self.parse)

    def request(self, url, callback, **kwargs):
        return scrapy.Request(url, callback=callback, errback=self.on_error, **kwargs)

    def on_error(self, failure):
        # DNS failure, timeout after retries, robots.txt block, ...
        self.logger.error("request failed: %s", failure.getErrorMessage())
        self.crawler.stats.inc_value("source/failed")

    def seen(self, n: int = 1):
        """Count rows the source returned *before* our entry-level filter.
        Lets the summary tell 'API returned nothing' from 'nothing matched'."""
        self.crawler.stats.inc_value("source/rows_seen", n)

    def make_item(self, **fields) -> InternshipItem:
        item = InternshipItem(
            source=self.name, company="", location="", description="",
            tags=[], posted_at="", remote=False,
        )
        item.update(fields)
        return item
