from .base import BROWSER_SETTINGS, InternshipSpider, clean, find_city, is_entry_level

NOT_JOBS = {"lancer 4k", "postuler", "voir l'offre", "voir plus", "en savoir plus"}


class RekruteSpider(InternshipSpider):
    """HTML scraping, Morocco's largest job board.

    One offer = one <li class="post-id"> holding <h2><a>title</a></h2>.
    Pages 1..N are requested concurrently (`scrapy crawl rekrute -a pages=5`).
    """
    name = "rekrute"
    custom_settings = BROWSER_SETTINGS
    url_template = "https://www.rekrute.com/offres.html?s=1&p={page}&o=1"

    def __init__(self, pages=3, **kwargs):
        super().__init__(**kwargs)
        self.pages = int(pages)

    async def start(self):
        for page in range(1, self.pages + 1):
            yield self.request(self.url_template.format(page=page), self.parse)

    def parse(self, response):
        lis = response.css("li.post-id")
        if not lis:  # fallback if the class disappears: any <li> with <h2><a>
            lis = response.xpath("//li[.//h2/a]")
        self.seen(len(lis))

        for li in lis:
            a = li.css("h2 a")
            if not a:
                continue
            title = clean("".join(a[0].xpath(".//text()").getall()))
            # guard against navigation text / buttons captured as "jobs"
            if len(title) < 8 or title.lower() in NOT_JOBS:
                continue
            href = a[0].attrib.get("href", "")

            info = li.css(".info, .desc, .job-description")
            description = clean("".join(info[0].xpath(".//text()").getall()))[:500] if info else ""

            location = "Morocco"
            loc_el = li.css(".location, em, .city")
            if loc_el:
                location = find_city("".join(loc_el[0].xpath(".//text()").getall()))
            if location == "Morocco" and description:
                location = find_city(description)

            li_text = " ".join(li.xpath(".//text()").getall()).lower()
            tags = ["morocco"]
            if "stage" in li_text:
                tags.append("stage")
            if "junior" in li_text:
                tags.append("junior")
            if "cdi" in li_text:
                tags.append("cdi")
            if "confirmé" in li_text:
                tags.append("senior")

            # keep entry-level; drop titles that clearly signal seniority
            if not is_entry_level(title):
                if any(k in title.lower() for k in ("senior", "expert", "confirmé", "lead")):
                    continue

            yield self.make_item(
                title=title,
                location=location,
                description=description,
                url=response.urljoin(href),
                tags=tags,
            )
