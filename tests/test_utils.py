import unittest
import os

from scrapy_testmaster.utils import clean_item
from .shared import Settings


class Config(object):
    SKIPPED_FIELDS = ["timestamp"]


settings1 = Settings()
config1 = Config()
cb_obj = {"a": "b", "timestamp": "xyz"}


class TestUtils(unittest.TestCase):
    clean_item(cb_obj, settings1, config1)
    def test_clean(self):
        self.assertDictEqual(cb_obj, {"a": "b"})