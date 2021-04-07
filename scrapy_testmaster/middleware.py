import os
import six
import pickle
import random
import logging
import copy

from scrapy.exceptions import NotConfigured
from scrapy.commands.genspider import sanitize_module_name
from scrapy.spiders import CrawlSpider
# from scrapy.utils.reqser import request_to_dict

from .utils import (
    add_sample,
    write_test,
    response_to_dict,
    get_or_create_test_dir,
    parse_request,
    clean_request,
    get_project_dirs,
    get_middlewares,
    create_dir,
    parse_callback_result,
    process_result
)
from .utils_novel import (
    get_cb_settings,
    validate_results,
    write_json,
    get_fixture_counts,
    update_max_fixtures,
    request_to_dict
)

logger = logging.getLogger(__name__)


def _copy_settings(settings, cb_settings):
    out = {}
    global_include = settings.getlist('TESTMASTER_INCLUDED_SETTINGS', [])
    try:
        local_include = cb_settings.INCLUDED_SETTINGS
    except:
        local_include = []
    include = local_include if local_include else global_include
    for name in include:
        out[name] = settings.get(name)
    return out


class TestMasterMiddleware:
    def __init__(self, crawler):
        settings = crawler.settings

        if not any(
            self.__class__.__name__ in s
            for s in settings.getwithbase('SPIDER_MIDDLEWARES').keys()
        ):
            raise ValueError(
                '%s must be in SPIDER_MIDDLEWARES' % (
                    self.__class__.__name__,))
        if not settings.getbool('TESTMASTER_ENABLED'):
            raise NotConfigured('scrapy-testmaster is not enabled')
        if settings.getint('CONCURRENT_REQUESTS') > 1:
            logger.warn(
                'Recording with concurrency > 1! '
                'Data races in shared object modification may create broken '
                'tests.'
            )

        self.max_fixtures = settings.getint(
            'TESTMASTER_MAX_FIXTURES_PER_CALLBACK',
            default=10
        )
        self.max_fixtures = \
            self.max_fixtures if self.max_fixtures >= 10 else 10

        self.base_path = settings.get(
            'TESTMASTER_BASE_PATH',
            default=os.path.join(get_project_dirs()[0], 'testmaster')
        )

        create_dir(self.base_path, exist_ok=True)

        self.init = 0
        self.fixture_counters = {}

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_spider_input(self, response, spider):
        if self.init == 0:
            if '_parse' in response.meta:
                spider_dir = os.path.join(self.base_path, 'tests', sanitize_module_name(spider.name))
                if os.path.exists(spider_dir):
                    self.fixture_counters = get_fixture_counts(
                        spider_dir, spider, spider.settings.get('TESTMASTER_EXTRA_PATH'))
            self.init += 1
        the_request = response.request
        # the parse command screws with middleware order because it uses essentially
        # two callbacks: a preliminary internal one and the real one. This is
        # grabbing the real callback from the meta.
        if '_parse' in response.meta and '_update' not in response.meta:
            the_request = response.request.copy()
            the_request.callback = response.meta['_callback']
            temp_meta = response.meta.copy()
            del temp_meta['_callback']
            the_request = the_request.replace(meta=temp_meta)

        _request = request_to_dict(the_request, spider=spider)
        if not _request['callback']:
            cb_name = 'parse'
        else:
            cb_name = _request['callback']
        test_dir = os.path.join(
            self.base_path, 'tests', sanitize_module_name(spider.name), cb_name)
        cb_settings = get_cb_settings(test_dir)
        filter_args = {'crawler', 'settings', 'start_urls'}
        if isinstance(spider, CrawlSpider):
            filter_args |= {'rules', '_rules'}
        response.meta['_testmaster'] = pickle.dumps({
            'request': parse_request(the_request, spider, cb_settings),
            'response': response_to_dict(response),
            'spider_args': {
                k: v for k, v in spider.__dict__.items()
                if k not in filter_args
            },
            'middlewares': get_middlewares(spider),
        })

        return None

    def process_spider_output(self, response, result, spider):
        input_data = pickle.loads(response.meta.pop('_testmaster'))
        request = input_data['request']
        callback_name = request['callback']

        settings = spider.settings
        test_dir, test_name = get_or_create_test_dir(
            self.base_path,
            sanitize_module_name(spider.name),
            callback_name,
            settings.get('TESTMASTER_EXTRA_PATH'),
        )
        cb_settings = get_cb_settings(test_dir)
        # parse command will return requests at the end of callbacks but not
        # items... As such I am processing the result as it comes, before it
        # reaches this point (and  storing the result in meta).
        if '_parse' in response.meta and '_update' not in response.meta:
            processed_result = response.meta.pop('_processed_result')
            out = result
        else:
            processed_result, out = parse_callback_result(result, spider, cb_settings)

        spider_attr_out = {
            k: v for k, v in spider.__dict__.items()
            if k not in ('crawler', 'settings', 'start_urls')
        }
        temp_rules = spider_attr_out.get('_rules', [])
        if temp_rules:
            spider_attr_out['_rules'] = [repr(rule) for rule in temp_rules]

        data = {
            'spider_name': spider.name,
            'request': request,
            'response': input_data['response'],
            'spider_args_out': spider_attr_out,
            'result': processed_result,
            'spider_args_in': input_data['spider_args'],
            'settings': _copy_settings(settings, cb_settings),
            'middlewares': input_data['middlewares'],
            'python_version': 2 if six.PY2 else 3,
        }

        callback_counter = self.fixture_counters.setdefault(callback_name, 0)
        # self.fixture_counters[callback_name] += 1

        index = 0

        max_fixtures = update_max_fixtures(cb_settings, self.max_fixtures)
        _request = copy.deepcopy(data['request'])
        _request = clean_request(_request, spider.settings, cb_settings)

        items_out, requests_out = process_result(
            data['result'], spider.settings, cb_settings)
        validate_results(test_dir, spider.settings, items_out, requests_out,
                         request['url'])

        if callback_counter < max_fixtures or '_update' in response.meta:
            index = callback_counter + 1
            if '_fixture' in response.meta:
                index = response.meta['_fixture']
            add_sample(index, test_dir, test_name, data)
            write_json(test_dir, _request, data['result'], index)

        else:
            # this random overwriting logic should only apply to generating testcases
            # via scrapy crawl
            if not ('_update' in response.meta or '_parse' in response.meta):
                r = random.randint(0, callback_counter)
                if r < max_fixtures:
                    index = r + 1
                    add_sample(index, test_dir, test_name, data)
                    write_json(test_dir, _request, data['result'], index)

        if index == 1:
            write_test(test_dir, test_name, request['url'])

        self.fixture_counters[callback_name] += 1

        # if we don't return an empty list here, 'update' keeps on making
        # requests indefinitely!
        if '_update' in response.meta:
            return []
        return out
