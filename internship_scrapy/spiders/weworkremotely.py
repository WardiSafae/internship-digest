from .base import InternshipSpider, is_entry_level


class WeWorkRemotelySpider(InternshipSpider):
    """RSS feed with a fallback URL: if the first feed gives no entry-level
    offer, the second one is tried."""
    name = "weworkremotely"
    feed_urls = [
        "https://weworkremotely.com/remote-jobs.rss",
        "https://weworkremotely.com/categories/remote-jobs.rss",
    ]

    async def start(self):
        yield self.request(self.feed_urls[0], self.parse, cb_kwargs={"next_idx": 1})

    def parse(self, response, next_idx):
        entries = response.xpath("//item")
        self.seen(len(entries))
        found = 0
        for it in entries:
            title = it.xpath("string(./title)").get()
            if not is_entry_level(title):
                continue
            found += 1
            yield self.make_item(
                title=title,
                company=it.xpath("string(./author | ./*[local-name()='creator'])").get(),
                location="Remote",
                description=it.xpath("string(./description)").get(),
                url=it.xpath("string(./link)").get(),
                posted_at=it.xpath("string(./pubDate)").get(),
                remote=True,
            )
        if not found and next_idx < len(self.feed_urls):
            yield self.request(self.feed_urls[next_idx], self.parse,
                               cb_kwargs={"next_idx": next_idx + 1})
