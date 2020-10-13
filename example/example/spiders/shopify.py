# -*- coding: utf-8 -*-
import scrapy
from scrapy.http import Request
from scrapy.exceptions import CloseSpider

from copy import deepcopy
import json
import logging
import re

class ShopifySpider(scrapy.Spider):
    name = 'shopify'
    PAGE_SIZE=250
    custom_settings = {
        "LOG_LEVEL": "DEBUG",
        "DOWNLOAD_DELAY": 5
    }

    def __init__(self,domains="colourpop.com,gymshark.com,cettire.com,jbhifi.com.au,fashionnova.com",**kwargs):
        if isinstance(domains, str):
            self.domains = domains.split(",")
        self.BASE_URLS = ['https://{}'.format(d) for d in self.domains]
        self.BASE_PROD_URLS = ['https://{}/products/'.format(d) + "{}" for d in self.domains]
    
    def start_requests(self):
        for i,base_url in enumerate(self.BASE_URLS):
            yield Request(
                url=base_url + "/products.json?limit=250&page=1",
                callback=self.parse_products,
                meta = {
                    "page": 1,
                    "categories": ["Shopify", base_url],
                    "prod_url": self.BASE_PROD_URLS[i]
                }
            )

    def parse_products(self,response): 
        metadata = response.meta
        page = metadata["page"]
        try:
            data = json.loads(response.text)
        except:
            self.logger.error("Error parsing page: {}".format(response.url))
            return
        products = data["products"]
        if not products:
            raise CloseSpider("Final page reached")

        for idx,base_item in enumerate(products):
            base_item["categories"] = metadata["categories"]
            try:
                base_item["url"] = metadata["prod_url"].format(base_item["handle"]) 
                try:
                    base_item["img"]=base_item["images"][0]["src"]
                except:
                    base_item["img"] = "n/a"
                base_item.pop("images", None)
                for variant in base_item["variants"]:
                    variant_item = deepcopy(base_item)
                    variant_item.pop("variants", None)
                    for key,val in variant.items():
                        if key in variant_item:
                            variant_item["variant_"+key] = val
                        else:
                            variant_item[key] = val
                    yield variant_item
            except Exception as e:
                self.logger.error("The product at index {} could not be parsed at {}. Error: {}".format(idx, response.url, e))
                continue
        
        metadata["page"] += 1
        url = response.url.replace("page={}".format(page), "page={}".format(page+1))
        yield response.request.replace(url=url, meta=metadata)