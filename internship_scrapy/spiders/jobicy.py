from .base import InternshipSpider, is_entry_level


class JobicySpider(InternshipSpider):
    name = "jobicy"
    start_urls = ["https://jobicy.com/api/v2/remote-jobs?count=100"]

    def parse(self, response):
        jobs = response.json().get("jobs", [])
        self.seen(len(jobs))
        for j in jobs:
            title = j.get("jobTitle", "")
            if not is_entry_level(title):
                continue
            yield self.make_item(
                title=title,
                company=j.get("companyName", ""),
                location=j.get("jobGeo", "Remote"),
                description=j.get("jobExcerpt", ""),
                url=j.get("url", ""),
                posted_at=j.get("pubDate", ""),
                remote=True,
            )
