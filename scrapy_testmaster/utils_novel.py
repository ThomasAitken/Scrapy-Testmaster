import os
import shutil
import importlib
import inspect
from glob import glob
import re
import json

from scrapy.http import Request
from scrapy.utils.python import to_unicode
from scrapy.utils.reqser import request_from_dict, _get_method
from scrapy.exceptions import _InvalidOutput, UsageError


def get_cb_settings(test_dir):
    config_path = os.path.join(test_dir, 'config.py')
    if not os.path.exists(config_path):
        return None
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    return config


def get_test_paths(spider_test_dir, spider_path, extra_path, fixture=False):
    poss_cb_names = get_callbacks(spider_path)
    dir_list = os.listdir(spider_test_dir)
    paths = []
    # assuming extra path in play
    if len(set(dir_list).intersection(set(poss_cb_names))) == 0:
        if extra_path:
            diff_path = os.path.join(spider_test_dir, extra_path)
            dir_list = os.listdir(diff_path)
            cb_list = filter(lambda d: '.' not in d, dir_list)
            for cb in cb_list:
                target = os.path.join(diff_path, cb)
                if fixture:
                    target = os.path.join(target, '*.bin')
                paths += glob(target)
    else:
        cb_list = filter(lambda d: '.' not in d, dir_list)
        for cb in cb_list:
            target = os.path.join(spider_test_dir, cb)
            if fixture:
                target = os.path.join(target, '*.bin')
            paths += glob(target)

    return paths


def update_max_fixtures(cb_settings, global_max_fixtures):
    try:
        max_fixtures = cb_settings.MAX_FIXTURES
        return max_fixtures
    except AttributeError:
        return global_max_fixtures


def get_num_fixtures(test_dir):
    if not os.path.exists(test_dir):
        return 0
    try:
        dir_list = os.listdir(test_dir)
        fixture_count = len(list(filter(lambda d: '.bin' in d, dir_list)))
    except IndexError:
        fixture_count = 0
    return fixture_count


def get_fixture_counts(spider_dir, spider, extra_path):
    fixture_counts = {}
    poss_cb_names = [name for name in dir(spider) if not name.startswith('__') and not
                     name == "start_requests" and callable(getattr(spider, name))]
    dir_list = os.listdir(spider_dir)
    # assuming extra path in play
    if len(set(dir_list).intersection(set(poss_cb_names))) == 0:
        if extra_path:
            new_path = os.path.join(spider_dir, extra_path)
            dir_list = os.listdir(new_path)
            cb_list = filter(lambda d: '.' not in d, dir_list)
            for cb in cb_list:
                test_dir = os.path.join(new_path, cb)
                fixture_counts[cb] = get_num_fixtures(test_dir)
        else:
            for cb in poss_cb_names:
                fixture_counts[cb] = 0
    else:
        for cb in filter(lambda d: '.' not in d, dir_list):
            test_dir = os.path.join(spider_dir, cb)
            fixture_counts[cb] = get_num_fixtures(test_dir)
    return fixture_counts


def basic_items_check(items, obligate_fields, primary_fields, request_url):
    for item in items:
        if not set(item.keys()).intersection(obligate_fields) == obligate_fields:
            missing_fields = obligate_fields.difference(item.keys())
            raise _InvalidOutput("Obligate fields check failed. Request url: %s. "
                                 "Missing fields: %s" % (request_url, missing_fields))
        for field in primary_fields:
            if not item.get(field, ""):
                raise _InvalidOutput("Primary fields check failed. Request url: %s. "
                                     "Empty field: %s" % (request_url, field))


def check_options(spider_settings, config, items, request_url):
    obligate_local = set()
    primary_local = set()
    obligate_global = set(spider_settings.getlist('TESTMASTER_OBLIGATE_ITEM_FIELDS', []))
    primary_global = set(spider_settings.getlist('TESTMASTER_PRIMARY_ITEM_FIELDS', []))
    if config is not None:
        try:
            obligate_local = set(config.OBLIGATE_ITEM_FIELDS)
        except AttributeError:
            pass
        try:
            primary_local = set(config.PRIMARY_ITEM_FIELDS)
        except AttributeError:
            pass
    obligate_fields = obligate_local if obligate_local else obligate_global
    primary_fields = primary_local if primary_local else primary_global
    basic_items_check(items, obligate_fields, primary_fields, request_url)


def check_global_rules(spider_settings, items, requests, request_url):
    path_to_rules = spider_settings.get('TESTMASTER_PATH_TO_RULES_FILE', None)
    if path_to_rules:
        try:
            module = importlib.import_module(path_to_rules.replace('/', '.'))
        except Exception as e:
            print(e)
            print("Rules file specified in project/spider "
                  "settings does not exist.")
        if hasattr(module, "ItemRules"):
            itemclass = module.ItemRules()
            check_item_rules(itemclass, items, request_url)
        if hasattr(module, "RequestRules"):
            reqclass = module.RequestRules()
            check_req_rules(reqclass, requests, request_url)


def check_local_rules(config, items, requests, request_url):
    try:
        itemclass = config.ItemRules()
        check_item_rules(itemclass, items, request_url)
    except AttributeError:
        pass
    try:
        reqclass = config.RequestRules()
        check_req_rules(reqclass, requests, request_url)
    except AttributeError:
        pass


def validate_results(test_dir, spider_settings, items, requests, request_url):
    config_path = os.path.join(test_dir, 'config.py')
    if not os.path.exists(config_path):
        config = None
    else:
        config = get_cb_settings(test_dir)

    check_options(spider_settings, config, items, request_url)
    check_local_rules(config, items, requests, request_url)
    check_global_rules(spider_settings, items, requests, request_url)


def check_item_rules(itemclass, items, request_url):
    itemclass_attrs = [(name, getattr(itemclass, name)) for name in dir(itemclass)
                       if not name.startswith('__')]
    item_rules = list(filter(lambda entry: callable(entry[1]), itemclass_attrs))
    for item in items:
        for rule_func in item_rules:
            try:
                rule_func[1](item)
            except AssertionError:
                raise _InvalidOutput("An item produced by the request with url %s has "
                                     "failed the rule %s" % (request_url, rule_func[0]))


def check_req_rules(reqclass, requests, request_url):
    reqclass_attrs = [(name, getattr(reqclass, name)) for name in dir(reqclass)
                      if not name.startswith('__')]
    req_rules = list(filter(lambda entry: callable(entry[1]), reqclass_attrs))
    for req in requests:
        for rule_func in req_rules:
            try:
                rule_func[1](req)
            except AssertionError:
                raise _InvalidOutput("A request produced by the request with url %s has "
                                     "failed the rule %s" % (request_url, rule_func[0]))


def _get_num_objects(result, _type):
    return len(list(filter(lambda entry: entry['type'] == _type, result)))


def write_json(test_dir, request, result, fixture_num):
    fixture = {}
    fixture["request"] = request
    fixture["num_items"] = _get_num_objects(result, "item")
    fixture["num_requests"] = _get_num_objects(result, "request")
    json_path = os.path.join(test_dir, 'view.json')
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            extant_fixtures = json.load(f)
        extant_fixtures[str(fixture_num)] = fixture

        with open(json_path, 'w') as f:
            json.dump(extant_fixtures, f)
    else:
        new_fixtures = {"1": fixture}
        with open(json_path, 'w') as f:
            json.dump(new_fixtures, f)


# The requests involved in the current fixtures will be written here, in JSON format
CURRENT_TESTS = [
    ''' {
        "url": "https://examplewebsite011235811.com",
        "headers": {"referer":"...", "content_type": "..."},
        "cookies": {},
        "method": "POST",
        "data": {"x": "y"},
        "type": "form",
        "meta": {"x": "y"},
        "fixture_num": 1
    },
    {
        ...
    }'''
]


# Simple and efficient regex!
# For a second I was considering loading in module = rookie thinking
def get_callbacks(spider_path):
    with open(spider_path, 'r') as spider_file:
        text = spider_file.read()
        callbacks = list(filter(lambda match: not(match.startswith('__') or match == 'start_requests'),
                                re.findall(r"def\s+(\w+)\([^\n]+response", text)))
        return callbacks


def write_config(path):
    config_file = os.path.join(path, 'config.py')
    config_src = os.path.dirname(__file__) + '/config_doc.py'
    shutil.copyfile(config_src, config_file)


def get_homepage_cookies(spider, mode=""):
    import requests
    user_agent = spider.settings.get('USER_AGENT')
    if len(spider.start_urls) == 1:
        inferred_homepage = spider.start_urls[0]
        r = requests.get(inferred_homepage, headers={"User-Agent": user_agent})
        print("HOMEPAGE STATUS CODE: %s" % str(r.status_code))
        return r.cookies.get_dict()
    else:
        if mode == "parse":
            raise UsageError("Homepage option selected but can't determine "
                             "homepage from start_urls %s" % spider.name,
                             print_help=False)
        print("Couldn't determine homepage to collect cookies from")
        return {}


def get_config_requests(test_dir, spider, max_fixtures):
    curr_fixture_count = get_num_fixtures(test_dir)
    config = get_cb_settings(test_dir)
    try:
        requests_to_add = config.REQUESTS_TO_ADD
    except AttributeError:
        return []

    defaults = {
        'method': 'GET', 'headers': None, 'body': None, 'cookies': None,
        'meta': None, '_encoding': 'utf-8', 'priority': 0, 'dont_filter': False,
        'errback': None, 'flags': None, 'cb_kwargs': None
    }
    complete_requests = []
    for req in requests_to_add:
        if curr_fixture_count < max_fixtures:
            for key, val in defaults.items():
                req[key] = req.get(key, val)
            req['callback'] = _get_method(spider, test_dir.split('/')[-1])
            req['meta']['_update'] = 1
            req['meta']['_fixture'] = curr_fixture_count + 1
            complete_requests.append(req)
            curr_fixture_count += 1
        else:
            break
    complete_requests = [request_from_dict(req) for req in complete_requests]
    return complete_requests


def get_reqs_multiple(test_paths, spider):
    requests = []
    for path in test_paths:
        requests += get_reqs_to_add(path, spider)
    return requests


def get_reqs_to_add(test_dir, spider):
    global_max_fixtures = spider.settings.getint(
        'TESTMASTER_MAX_FIXTURES_PER_CALLBACK',
        default=10
    )
    cb_settings = get_cb_settings(test_dir)
    max_fixtures = update_max_fixtures(cb_settings, global_max_fixtures)
    return get_config_requests(test_dir, spider, max_fixtures)


def trigger_requests(crawler_process, spider, requests):
    spider_loader = crawler_process.spider_loader
    spidercls = spider_loader.load(spider.name)
    spidercls.start_requests = lambda s: requests
    crawler_process.crawl(spidercls)
    crawler_process.start()


def cascade_fixtures(test_dir, min_fixture_cleared):
    fixtures = list(filter(lambda d: '.bin' in d, os.listdir(test_dir)))
    fixtures_store = [(f, int(re.search(r'(\d+)\.bin', f).group(1))) for f in
                      fixtures]
    fixtures_to_move = list(filter(lambda f: f[1] > min_fixture_cleared,
                                   fixtures_store))
    fixtures_to_move.sort(key=lambda f: f[1])
    json_path = os.path.join(test_dir, 'view.json')
    with open(json_path, 'r') as f:
        curr_json = json.load(f)
    new_num = min_fixture_cleared
    for name, num in fixtures_to_move:
        os.rename(os.path.join(test_dir, name),
                  os.path.join(test_dir, 'fixture%d.bin' % new_num))
        curr_json[str(new_num)] = curr_json[str(num)]
        del curr_json[str(num)]
        new_num += 1
    with open(json_path, 'w') as f:
        json.dump(curr_json, f)


# This and the next function are extremely similar to functions found in
# scrapy/utils/reqser.py. In fact, this 'request_to_dict' function is unchanged.
# What I changed was the helper function '_find_method', replacing "if func_self
# is obj:" with "if type(func_self) is type(obj):". This is because I found that
# for the update command, the callback that became attached to the request via
# the call of request_from_dict in cli.py was bound to a spider instance
# different from the spider instance that I started running via the above
# function, and so request_to_dict in process_spider_input was failing
# (specifically, func_self (spider instance 1) was registering as different from
# obj (spider instance 2)). Checking more simply that both are instances of the
# same spider class seems to solve the problem without breaking anything!


def request_to_dict(request, spider=None):
    """Convert Request object to a dict.

    If a spider is given, it will try to find out the name of the spider method
    used in the callback and store that as the callback.
    """
    cb = request.callback
    if callable(cb):
        cb = _find_method(spider, cb)
    eb = request.errback
    if callable(eb):
        eb = _find_method(spider, eb)
    d = {
        'url': to_unicode(request.url),  # urls should be safe (safe_string_url)
        'callback': cb,
        'errback': eb,
        'method': request.method,
        'headers': dict(request.headers),
        'body': request.body,
        'cookies': request.cookies,
        'meta': request.meta,
        '_encoding': request._encoding,
        'priority': request.priority,
        'dont_filter': request.dont_filter,
        'flags': request.flags,
        'cb_kwargs': request.cb_kwargs,
    }
    if type(request) is not Request:
        d['_class'] = request.__module__ + '.' + request.__class__.__name__
    return d


def _find_method(obj, func):
    if obj:
        try:
            func_self = func.__self__
        except AttributeError:  # func has no __self__
            pass
        else:
            if type(func_self) is type(obj):
                members = inspect.getmembers(obj, predicate=inspect.ismethod)
                for name, obj_func in members:
                    # We need to use __func__ to access the original
                    # function object because instance method objects
                    # are generated each time attribute is retrieved from
                    # instance.
                    #
                    # Reference: The standard type hierarchy
                    # https://docs.python.org/3/reference/datamodel.html
                    if obj_func.__func__ is func.__func__:
                        return name
            else:
                print(func_self, "func_self is not obj!!!!!!")
    raise ValueError("Function %s is not a method of: %s" % (func, obj))
