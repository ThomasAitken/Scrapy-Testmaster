from __future__ import print_function
import os
import json
import logging
import copy

from scrapy.commands.genspider import sanitize_module_name
from scrapy.http import Request
from scrapy.item import Item
from scrapy.utils import display
from scrapy.utils.conf import arglist_to_dict
from scrapy.utils.spider import iterate_spider_output, spidercls_for_request
from scrapy.exceptions import UsageError

from .utils import parse_request, get_project_dirs
from .utils_novel import get_cb_settings, get_homepage_cookies

logger = logging.getLogger(__name__)

# requires_project = True

spidercls = None
crawler_process = None
pcrawler = None

# spider = None
items = {}
requests = {}

first_response = None


def syntax():
    return "[options] <urls>"


def short_desc():
    return "Parse URLs (using its spider) and print the results"


def max_level():
    global items, requests
    max_items, max_requests = 0, 0
    if items:
        max_items = max(items)
    if requests:
        max_requests = max(requests)
    return max(max_items, max_requests)


def add_items(lvl, new_items, remembered_items):
    global items
    old_items = remembered_items.get(lvl, [])
    items[lvl] = old_items + new_items


def add_requests(lvl, new_reqs):
    global requests
    old_reqs = requests.get(lvl, [])
    requests[lvl] = old_reqs + new_reqs


def print_items(lvl=None, colour=True):
    global items
    if lvl is None:
        items_out = [item for lst in items.values() for item in lst]
    else:
        items_out = items.get(lvl, [])

    print("# Scraped Items ", "-" * 60)
    display.pprint([dict(x) for x in items_out], colorize=colour)


def print_requests(lvl=None, colour=True):
    global requests
    if lvl is None:
        if requests:
            requests_out = requests[max(requests)]
        else:
            requests_out = []
    else:
        requests_out = requests.get(lvl, [])

    print("# Requests ", "-" * 65)
    display.pprint(requests_out, colorize=colour)


def print_results(args):
    colour = not args.nocolour

    if args.verbose:
        for level in range(1, max_level() + 1):
            print('\n>>> DEPTH LEVEL: %s <<<' % level)
            if not args.noitems:
                print_items(level, colour)
            if not args.nolinks:
                print_requests(level, colour)
    else:
        print('\n>>> STATUS DEPTH LEVEL %s <<<' % max_level())
        if not args.noitems:
            print_items(colour=colour)
        if not args.nolinks:
            print_requests(colour=colour)


def run_callback(response, callback, cb_kwargs=None):
    cb_kwargs = cb_kwargs or {}
    items, requests = [], []

    for x in iterate_spider_output(callback(response, **cb_kwargs)):
        if isinstance(x, (Item, dict)):
            items.append(x)
        elif isinstance(x, Request):
            requests.append(x)
    return items, requests


def get_callback_from_rules(spider, request):
    if getattr(spider, 'rules', None):
        for rule in spider.rules:
            if rule.link_extractor.matches(request.url):
                return rule.callback or "parse"
    else:
        logger.error('No CrawlSpider rules found in spider %(spider)r, '
                     'please specify a callback to use for parsing',
                     {'spider': spider.name})


def set_spidercls(url_list, args):
    global crawler_process, spidercls
    spider_loader = crawler_process.spider_loader
    if args.spider:
        try:
            spidercls = spider_loader.load(args.spider)
        except KeyError:
            logger.error('Unable to find spider: %(spider)s',
                         {'spider': args.spider})
    else:
        spidercls = spidercls_for_request(spider_loader, Request(url_list[0]))
        if not spidercls:
            logger.error('Unable to find spider for: %(url)s', {'url': url_list[0]})

    # Request requires callback argument as callable or None, not string
    request_list = []
    for url in url_list:
        request_list.append(Request(url, None))

    _start_requests = lambda s: [prepare_request(s, request, args) for request in request_list]
    spidercls.start_requests = _start_requests


def start_parsing(url_list, args):
    global crawler_process, spidercls, first_response, pcrawler
    crawler_process.crawl(spidercls, **args.spargs)
    pcrawler = list(crawler_process.crawlers)[0]
    crawler_process.start()

    if not first_response:
        logger.error('No response downloaded for: %(url)s',
                     {'url': url_list[0]})


def process_result_for_middleware(spider, callback, items, requests):
    processed_result = []
    for item in items:
        processed_result.append({'type': 'item', 'data': item})
    for req in requests:
        base_path = os.path.join(get_project_dirs()[0], 'testmaster')
        test_dir = os.path.join(base_path, 'tests', sanitize_module_name(spider.name), callback.__name__)
        cb_settings = None
        if os.path.exists(test_dir):
            cb_settings = get_cb_settings(test_dir)
        processed_result.append({'type': 'request', 'data': parse_request(req, spider, cb_settings)})
    return processed_result


def prepare_request(spider, request, args):
    def callback(response, **cb_kwargs):
        global items, first_response, pcrawler
        # memorize first request
        if not first_response:
            first_response = response

        # real callback
        cb = response.meta['_callback']
        if not cb:
            print("UNEXPECTED FATAL ERROR")
        # surplus to requirements
        del response.meta['_callback']
        # restoring this to the 'proper' value because spider logic may rely on
        # the accuracy of this attribute
        response.request.callback = cb

        # parse items and requests
        depth = response.meta['_depth']

        remembered_items = copy.deepcopy(items)
        itemz, requests = run_callback(response, cb, cb_kwargs)
        if args.pipelines:
            itemproc = pcrawler.engine.scraper.itemproc
            for item in itemz:
                itemproc.process_item(item, spider)
        # print(items)
        add_items(depth, itemz, remembered_items)
        add_requests(depth, requests)

        response.meta["_processed_result"] = process_result_for_middleware(spider, cb, itemz, requests)

        if depth < args.depth:
            for req in requests:
                req.meta['_depth'] = depth + 1
                req.meta['_callback'] = req.callback
                req.meta['_parse'] = 1
                req.callback = callback
            return requests

    # update request headers if any headers passed through the --headers opt
    if args.headers:
        request.headers.update(args.headers)

    # update request meta if any extra meta was passed through the --meta/-m args.
    if args.meta:
        request.meta.update(args.meta)

    if args.homepage:
        request.cookies = get_homepage_cookies(spider, mode="parse")

    # update request cookies if any cookies passed through the --cookies opt
    if args.cookies:
        request.cookies = args.cookies

    # update request method if any method was passed through --method
    if args.method:
        if args.method.upper() == 'POST':
            request.method = 'POST'

    # update cb_kwargs if any extra values were was passed through the --cbkwargs option.
    if args.cbkwargs:
        request.cb_kwargs.update(args.cbkwargs)

    # get real callback
    if args.callback:
        cb = args.callback
    elif args.rules and not first_response:
        if not cb:
            cb = get_callback_from_rules(spider, request)
            if not cb:
                logger.error('Cannot find a rule that matches %(url)r in spider: %(spider)s',
                             {'url': request.url, 'spider': spider.name})
                return
    else:
        cb = 'parse'

    if not callable(cb):
        cb_method = getattr(spider, cb, None)
        if callable(cb_method):
            cb = cb_method
        else:
            logger.error('Cannot find callback %(callback)r in spider: %(spider)s',
                         {'callback': cb, 'spider': spider.name})
            return

    request.meta['_depth'] = 1
    request.meta['_callback'] = cb
    request.meta['_parse'] = 1
    request.callback = callback
    return request


def process_options(args):
    process_spider_arguments(args)
    process_request_headers(args)
    process_request_meta(args)
    process_request_cookies(args)
    process_request_cb_kwargs(args)
    return args


def process_spider_arguments(args):
    try:
        args.spargs = arglist_to_dict(args.spargs)
    except ValueError:
        raise UsageError("Invalid -a value, use -a NAME=VALUE", print_help=False)


def process_request_headers(args):
    if args.headers:
        try:
            args.headers = json.loads(args.headers)
        except ValueError:
            raise UsageError("Invalid --headers value, pass a valid json string to --headers. "
                             "Example: --headers='{\"foo\" : \"bar\"}'", print_help=False)


def process_request_meta(args):
    if args.meta:
        try:
            args.meta = json.loads(args.meta)
        except ValueError:
            raise UsageError("Invalid -m/--meta value, pass a valid json string to -m or --meta. "
                             "Example: --meta='{\"foo\" : \"bar\"}'", print_help=False)


def process_request_cookies(args):
    if args.cookies:
        try:
            args.cookies = json.loads(args.cookies)
        except ValueError:
            raise UsageError("Invalid --cookies value, pass a valid json string to --cookies. "
                             "Example: --cookies='{\"foo\" : \"bar\"}'", print_help=False)


def process_request_cb_kwargs(args):
    if args.cbkwargs:
        try:
            args.cbkwargs = json.loads(args.cbkwargs)
        except ValueError:
            raise UsageError("Invalid --cbkwargs value, pass a valid json string to --cbkwargs. "
                             "Example: --cbkwargs='{\"foo\" : \"bar\"}'", print_help=False)


def run_command(crawl_process, url_list, args):
    # prepare spidercls
    global crawler_process, spidercls
    crawler_process = crawl_process
    set_spidercls(url_list, args)

    if spidercls and args.depth > 0:
        start_parsing(url_list, args)
        print_results(args)
