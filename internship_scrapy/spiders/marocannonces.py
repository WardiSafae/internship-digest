from urllib.parse import urljoin

from .base import BROWSER_SETTINGS, InternshipSpider, clean, find_city


class MarocAnnoncesSpider(InternshipSpider):
    """HTML scraping, classifieds site with an Emploi section.

    Offers are found by URL pattern (links containing /annonce/), which is
    more stable than CSS class names. The page lists them with *relative*
    hrefs without a leading slash ("categorie/309/..."), which are paths from
    the site root, so they are joined to the root explicitly. (The
    requests-based version stored them as-is, i.e. as broken relative links.)
    """
    name = "marocannonces"
    custom_settings = BROWSER_SETTINGS
    site_root = "https://www.marocannonces.com/"
    page_urls = [
        "https://www.marocannonces.com/maroc/emploi.html",
        "https://www.marocannonces.com/categorie/309/Emploi/Offres-emploi.html",
    ]

    async def start(self):
        yield self.request(self.page_urls[0], self.parse, cb_kwargs={"next_idx": 1})

    def parse(self, response, next_idx):
        links = [a for a in response.css("a[href*='/annonce/']")
                 if len(clean("".join(a.xpath(".//text()").getall()))) > 5]
        self.seen(len(links))

        if not links and next_idx < len(self.page_urls):   # fallback page
            yield self.request(self.page_urls[next_idx], self.parse,
                               cb_kwargs={"next_idx": next_idx + 1})
            return

        for a in links[:60]:
            title = clean("".join(a.xpath(".//text()").getall()))
            # the site glues the city to the title: "Chargé(e) de Paie /BerrechidBerrechid"
            location = find_city(title)

            company = ""
            parent = a.xpath("ancestor::*[self::div or self::li or self::article][1]")
            if parent:
                comp = parent[0].css(".company, .advertiser, b")
                if comp:
                    company = clean("".join(comp[0].xpath(".//text()").getall()))

            yield self.make_item(
                title=title,
                company=company,
                location=location,
                url=urljoin(self.site_root, a.attrib["href"]),
                tags=["morocco"],
            )
