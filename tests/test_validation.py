import unittest
import os

from scrapy_testmaster.utils_novel import validate_results
from scrapy.exceptions import _InvalidOutput

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

def write_config(file_string):
    with open('config.py', 'w') as f:
        f.write(file_string)

def del_config():
    os.remove('config.py')

class Settings(object):
    TESTMASTER_OBLIGATE_ITEM_FIELDS = ["name"]

    def getlist(self, attr_name, default=[]):
        try:
            return getattr(self, attr_name)
        except AttributeError:
            return default
    
    def get(self, attr_name, default=None):
        try:
            return getattr(self, attr_name)
        except AttributeError:
            return default

result = [{"type": "item", "data": {"name": ""}}, {"type": "request", "data": {}}]
spider_settings = Settings()


class TestValidation(unittest.TestCase):
    def test_conflict(self):
        write_config(config_1)
        with self.assertRaises(_InvalidOutput):
            validate_results('', spider_settings, result, '')
        del_config()

    def test_item_rule(self):
        write_config(config_2)
        with self.assertRaises(_InvalidOutput):
            validate_results('', spider_settings, result, '')
        del_config()


# if __name__ == '__main__':
#     unittest.main()