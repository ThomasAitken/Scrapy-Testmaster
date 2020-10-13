# THIS IS A GENERATED FILE
# Generated by: scrapy crawl shopify  # noqa: E501
# Request URL: https://colourpop.com/products.json?limit=250&page=1  # noqa: E501
import os
import unittest
from scrapy_testmaster.utils import generate_test


class TestMaster(unittest.TestCase):
    def test__shopify__parse_products(self):
        files = os.listdir(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
        files = [f for f in files if f.endswith('.bin')]
        self.maxDiff = None
        for f in files:
            file_path = os.path.join(os.path.dirname(__file__), f)
            print("Testing fixture '%s'" % (f))
            test = generate_test(os.path.abspath(file_path))
            test(self)


if __name__ == '__main__':
    unittest.main()
