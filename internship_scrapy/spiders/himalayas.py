from .base import InternshipSpider, is_entry_level


class HimalayasSpider(InternshipSpider):
    name = "himalayas"
    start_urls = ["https://himalayas.app/jobs/api?limit=100"]

    def parse(self, response):
        data = response.json()
        rows = data.get("jobs") or data.get("data") or []
        self.seen(len(rows))
        for j in rows:
            title = j.get("title") or j.get("jobTitle", "")
            if not is_entry_level(title):
                continue
            yield self.make_item(
                title=title,
                company=j.get("companyName") or j.get("company", ""),
                location=j.get("location") or j.get("jobGeo", "Remote"),
                description=j.get("description", ""),
                url=j.get("applicationLink") or j.get("url", ""),
                tags=j.get("categories", []) or [],
                posted_at=str(j.get("pubDate", "")),
                remote=True,
            )
