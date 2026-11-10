from .base import InternshipSpider, is_entry_level


class WorkingNomadsSpider(InternshipSpider):
    name = "working_nomads"
    start_urls = ["https://www.workingnomads.com/api/exposed_jobs/"]

    def parse(self, response):
        rows = response.json()
        self.seen(len(rows))
        for j in rows:
            title = j.get("title", "")
            if not is_entry_level(title):
                continue
            yield self.make_item(
                title=title,
                company=j.get("company_name", ""),
                location=j.get("location", "Remote"),
                description=j.get("description", ""),
                url=j.get("url", ""),
                tags=j.get("tags", []) or [],
                posted_at=j.get("pub_date", ""),
                remote=True,
            )
