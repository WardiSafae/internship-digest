from .base import InternshipSpider


class RemotiveSpider(InternshipSpider):
    """JSON API. The server already filters with ?search=intern."""
    name = "remotive"
    start_urls = ["https://remotive.com/api/remote-jobs?search=intern"]

    def parse(self, response):
        jobs = response.json().get("jobs", [])
        self.seen(len(jobs))
        for j in jobs:
            yield self.make_item(
                title=j.get("title", ""),
                company=j.get("company_name", ""),
                location=j.get("candidate_required_location", "Remote"),
                description=j.get("description", ""),
                url=j.get("url", ""),
                tags=j.get("tags", []),
                posted_at=j.get("publication_date", ""),
                remote=True,
            )
