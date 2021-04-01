import unittest

from scrapy_testmaster.utils_novel import validate_results
from scrapy.exceptions import _InvalidOutput
from .shared import Settings, write_config, del_config

config_1 = '''
PRIMARY_ITEM_FIELDS = ["name"]
'''
config_2 = '''
class ItemRules(object):
    def basic_rule(self, item):
        assert(item["name"]),"Fail"

class RequestRules(object):
    def basic_rule(self, request):
        assert("meta" in request),"Fail"
'''
config_3 = '''
PRIMARY_ITEM_FIELDS = ["cool"]
'''


class Settings1(Settings):
    TESTMASTER_OBLIGATE_ITEM_FIELDS = ["name"]


class Settings2(Settings):
    TESTMASTER_PRIMARY_ITEM_FIELDS = ["uncool"]


items1 = [{"name": ""}]
requests = [{}]
spider_settings1 = Settings1()

spider_settings2 = Settings2()
items2 = [{"uncool": "1"}]
items3 = [{"cool": "1"}]


class TestValidation(unittest.TestCase):
    def test_conflict(self):
        write_config(config_1)
        with self.assertRaises(_InvalidOutput):
            validate_results('', spider_settings1, items1, requests, '')
        del_config()

    def test_item_rule(self):
        write_config(config_2)
        with self.assertRaises(_InvalidOutput):
            validate_results('', spider_settings1, items1, requests, '')
        del_config()

    def test_override1(self):
        write_config(config_3)
        with self.assertRaises(_InvalidOutput):
            validate_results('', spider_settings2, items2, requests, '')
        del_config()

    def test_override2(self):
        write_config(config_3)
        validate_results('', spider_settings2, items3, requests, '')
        del_config()
