import copy
import datetime
import unittest

from scrapy_testmaster.utils import clean_item, clean_request
from .shared import Settings


class Config1(object):
    SKIPPED_FIELDS = ["timestamp", "nested/item"]
    SKIPPED_FIELDS_DELIMITER = "/"
    REQUEST_SKIPPED_FIELDS = ["meta+nested+item"]
    REQUEST_SKIPPED_FIELDS_DELIMITER = "+"


class Config2(object):
    INCLUDED_AUTH_HEADERS = ["Authorization"]


settings1 = Settings()
config1 = Config1()
config2 = Config2()
cb_obj = {
    "a": "b",
    "timestamp": "xyz",
    "nested": {
        "item": 20
    }
}
ugly_request = {
    "url": "https://examplewebsite011235811.com",
    "coolkey": b"bytestringexample",
    "headers": {
        "coolkey": [b"bytestringexample"],
        "Authorization": [b"Basic auth"]
    },
    "meta": {
        "date": datetime.date.today(),
        "splash": {
            "splash_headers": {
                "Authorization": b"Basic auth"
            }
        },
        "nested": {
            "item": 10
        }
    }
}


class TestUtils(unittest.TestCase):
    clean_item(cb_obj, settings1, config1)

    def test_clean_item(self):
        self.assertDictEqual(cb_obj, {"a": "b", "nested": {}})

    def test_clean_request(self):
        temp_req = copy.deepcopy(ugly_request)
        shiny_req = clean_request(temp_req, settings1, config1)
        self.assertDictEqual(
            shiny_req,
            {
                "url": "https://examplewebsite011235811.com",
                "coolkey": "bytestringexample",
                "headers": {
                    "coolkey": "bytestringexample"
                },
                "meta": {
                    "date": str(datetime.date.today()),
                    "splash": {
                        "splash_headers": {}
                    },
                    "nested": {}
                }
            })

    def test_clean_with_auth(self):
        temp_req = copy.deepcopy(ugly_request)
        shiny_req = clean_request(temp_req, settings1, config2)
        self.assertDictEqual(
            shiny_req,
            {
                "url": "https://examplewebsite011235811.com",
                "coolkey": "bytestringexample",
                "headers": {
                    "coolkey": "bytestringexample",
                    "Authorization": "Basic auth"
                },
                "meta": {
                    "date": str(datetime.date.today()),
                    "splash": {
                        "splash_headers": {
                            "Authorization": "Basic auth"
                        }
                    },
                    "nested": {
                        "item": 10
                    }
                }
            })
