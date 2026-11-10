from .base import InternshipSpider, is_entry_level


class ArbeitnowSpider(InternshipSpider):
    """JSON API, general feed -> we filter entry-level titles ourselves."""
    name = "arbeitnow"
    start_urls = ["https://www.arbeitnow.com/api/job-board-api"]

    def parse(self, response):
        rows = response.json().get("data", [])
        self.seen(len(rows))
        for j in rows:
            title = j.get("title", "")
            if not is_entry_level(title):
                continue
            yield self.make_item(
                title=title,
                company=j.get("company_name", ""),
                location=j.get("location", ""),
                description=j.get("description", ""),
                url=j.get("url", ""),
                tags=j.get("tags", []),
                posted_at=str(j.get("created_at", "")),
                remote=j.get("remote", False),
            )
