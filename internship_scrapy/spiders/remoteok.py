from .base import InternshipSpider, is_entry_level


class RemoteOKSpider(InternshipSpider):
    """JSON API. The first element of the list is legal metadata, not a job."""
    name = "remoteok"
    start_urls = ["https://remoteok.com/api"]

    def parse(self, response):
        data = response.json()
        rows = data[1:] if isinstance(data, list) else []
        self.seen(len(rows))
        for j in rows:
            title = j.get("position", "")
            tags = [t.lower() for t in (j.get("tags") or [])]
            if not is_entry_level(title + " " + " ".join(tags)):
                continue
            yield self.make_item(
                title=title,
                company=j.get("company", ""),
                location=j.get("location", "Remote"),
                description=j.get("description", ""),
                url=j.get("url", ""),
                tags=j.get("tags", []),
                posted_at=str(j.get("date", "")),
                remote=True,
            )
