# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
from scrapy.exceptions import DropItem

class ExamplePipeline:
    def __init__(self):
        self.ids_seen = set()

    def process_item(self, item, spider):
        key = "id" if "variant_id" not in item else "variant_id"
        item_id = item[key]
        if item_id in self.ids_seen:
            raise DropItem("Duplicate item found: %s" % item_id)
        else:
            self.ids_seen.add(item_id)
            return item