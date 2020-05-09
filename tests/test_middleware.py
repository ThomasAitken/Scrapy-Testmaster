from scrapy_testmaster.middleware import TestMasterMiddleware


class DelAttrTestMasterMiddleware(TestMasterMiddleware, object):

    def process_spider_output(self, response, result, spider):
        if hasattr(spider, 'test_attr'):
            delattr(spider, 'test_attr')

        return super(self.__class__, self).process_spider_output(response,
                                                                 result,
                                                                 spider)


class DelObjectsTestMasterMiddleware(TestMasterMiddleware, object):

    def process_spider_output(self, response, result, spider):
        result = []
        return super(self.__class__, self).process_spider_output(response,
                                                                 result,
                                                                 spider)
