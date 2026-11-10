"""The one data model shared by every spider.

Same columns as the `internships` table, so a spider's output maps 1:1
onto the database row (the `id` is filled in by IdPipeline).
"""
import scrapy


class InternshipItem(scrapy.Item):
    id = scrapy.Field()
    title = scrapy.Field()
    company = scrapy.Field()
    location = scrapy.Field()
    description = scrapy.Field()
    url = scrapy.Field()
    source = scrapy.Field()
    tags = scrapy.Field()
    posted_at = scrapy.Field()
    remote = scrapy.Field()
