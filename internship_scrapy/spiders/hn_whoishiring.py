from urllib.parse import urlencode

from parsel import Selector

from .base import InternshipSpider, clean, is_entry_level


class HNWhoIsHiringSpider(InternshipSpider):
    """Two chained requests (this is where Scrapy callbacks are handy):

    1. Algolia search  -> id of the latest "Ask HN: Who is hiring?" thread
    2. Algolia items/<id> -> the thread's comments, each one a job post
    """
    name = "hn_whoishiring"
    search_url = "https://hn.algolia.com/api/v1/search_by_date?" + urlencode({
        "query": "Ask HN: Who is hiring?", "tags": "story", "hitsPerPage": 1})
    thread_url = "https://hn.algolia.com/api/v1/items/{id}"

    async def start(self):
        yield self.request(self.search_url, self.parse)

    def parse(self, response):
        hits = response.json().get("hits", [])
        if not hits:
            self.logger.warning("no 'Who is hiring?' thread found")
            return
        yield self.request(self.thread_url.format(id=hits[0]["objectID"]),
                           self.parse_thread)

    def parse_thread(self, response):
        children = response.json().get("children", [])
        self.seen(len(children))
        for c in children:
            html = c.get("text") or ""
            if not is_entry_level(html):
                continue
            # Comments are HTML fragments: keep only the text.
            plain = clean(Selector(text=html).xpath("string()").get())
            yield self.make_item(
                title=plain[:120],
                description=plain[:2000],
                url=f"https://news.ycombinator.com/item?id={c['id']}",
            )
