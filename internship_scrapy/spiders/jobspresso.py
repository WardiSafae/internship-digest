from .base import InternshipSpider


class JobspressoSpider(InternshipSpider):
    """RSS feed. The URL already restricts to the internship category."""
    name = "jobspresso"
    start_urls = ["https://jobspresso.co/?feed=job_feed&job_categories=internship"]

    def parse(self, response):
        items = response.xpath("//item")
        self.seen(len(items))
        for it in items:
            yield self.make_item(
                title=it.xpath("string(./title)").get(),
                location="Remote",
                description=it.xpath("string(./description)").get(),
                url=it.xpath("string(./link)").get(),
                posted_at=it.xpath("string(./pubDate)").get(),
                remote=True,
            )
