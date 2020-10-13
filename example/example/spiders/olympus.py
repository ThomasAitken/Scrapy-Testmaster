# -*- coding: utf-8 -*-
import scrapy
from scrapy.http import Request, FormRequest
import re
from urllib.parse import urljoin

class OlympusSpider(scrapy.Spider):
    name = 'olympus'
    allowed_domains = ['olympus.realpython.org']
    start_urls = ['http://olympus.realpython.org/profiles']
    BASE_URL = 'http://olympus.realpython.org/'
    item_id = 1

    def parse(self, response):
        gods = response.xpath("//h2/a")
        for g in gods:
            url = urljoin(self.BASE_URL, g.xpath("./@href").extract_first(default="").strip())
            categories = ["Gods", g.xpath("./text()").extract_first(default="").strip()]
            yield Request(
                url,
                callback=self.parse_info,
                meta = {
                    "categories": categories
                }
            )

    def parse_info(self, response):
        item = {}
        item["categories"] = response.meta["categories"]
        text = [t.strip() for t in filter(lambda t: t.strip() != "", response.xpath("//center//text()").extract())]
        for t in text:
            key,val = t.split(': ')
            item[key] = val
        item["id"] = self.item_id
        self.item_id += 1
        yield item
        # item["fav_animal"] = re.search(r'')

    def parse_login(self, response, **kwargs):
        print(response.status)
        return

