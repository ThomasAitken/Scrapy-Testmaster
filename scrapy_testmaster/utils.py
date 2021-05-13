import os
import sys
import copy
import zlib
import pickle
import json
import shutil
from importlib import import_module
from itertools import islice

from .utils_novel import get_cb_settings, request_to_dict, validate_results

import six
from scrapy import signals
from scrapy.crawler import Crawler
from scrapy.exceptions import NotConfigured, _InvalidOutput
from scrapy.http import Request, Response
from scrapy.item import Item
from scrapy.utils.conf import (build_component_list, closest_scrapy_cfg,
                               init_env)
from scrapy.utils.misc import arg_to_iter, load_object, walk_modules
from scrapy.utils.project import get_project_settings
from scrapy.utils.python import to_bytes
from scrapy.utils.reqser import request_from_dict
from scrapy.utils.spider import iter_spider_classes

import datadiff.tools

NO_ITEM_MARKER = object()
FIXTURE_VERSION = 1


def auto_import(qualified_name):
    mod_name, class_name = qualified_name.rsplit('.', 1)
    return getattr(import_module(mod_name), class_name)


def create_instance(objcls, settings, crawler, *args, **kwargs):
    if settings is None:
        if crawler is None:
            raise ValueError("Specifiy at least one of settings and crawler.")
        settings = crawler.settings
    if crawler and hasattr(objcls, 'from_crawler'):
        return objcls.from_crawler(crawler, *args, **kwargs)
    elif hasattr(objcls, 'from_settings'):
        return objcls.from_settings(settings, *args, **kwargs)
    else:
        return objcls(*args, **kwargs)


def get_project_dirs():
    outer_dir = inner_dir = ""
    closest_cfg = closest_scrapy_cfg()
    if closest_cfg:
        outer_dir = os.path.dirname(closest_cfg)
    if os.environ.get('SCRAPY_PROJECT'):
        inner_dir = os.environ.get('SCRAPY_PROJECT')
    if outer_dir and inner_dir:
        return (outer_dir, inner_dir)

    init_env()
    scrapy_module = os.environ.get('SCRAPY_SETTINGS_MODULE')
    if scrapy_module is None and not outer_dir:
        raise Exception("Project configuration awry")
    if not inner_dir:
        inner_dir = scrapy_module.split('.')[0]
    if outer_dir and inner_dir:
        return (outer_dir, inner_dir)

    try:
        module = import_module(scrapy_module)
        outer_dir = os.path.dirname(os.path.dirname(module.__file__))
        return (outer_dir, inner_dir)
    except ImportError:
        raise Exception("Project configuration awry")


def get_middlewares(spider):
    full_list = build_component_list(
        spider.settings.getwithbase('SPIDER_MIDDLEWARES'))
    testmaster_mw_path = list(filter(
        lambda x: x.endswith('TestMasterMiddleware'), full_list))[0]
    start = full_list.index(testmaster_mw_path)
    mw_paths = [mw for mw in full_list[start:] if mw != testmaster_mw_path]

    return mw_paths


def create_dir(path, parents=False, exist_ok=False):
    try:
        if parents:
            os.makedirs(path)
        else:
            os.mkdir(path)
    except OSError:
        if not exist_ok:
            raise


def get_or_create_test_dir(base_path, spider_name, callback_name, extra=None):
    components = [base_path, 'tests', spider_name]
    if extra:
        components.append(extra)
    components.append(callback_name)
    test_dir = None
    for component in components:
        test_dir = os.path.join(test_dir, component) if test_dir else component
        create_dir(test_dir, parents=True, exist_ok=True)
        init_file = os.path.join(test_dir, '__init__.py')
        with open(init_file, 'a'):
            os.utime(init_file, None)

    test_name = '__'.join(components[2:])
    return test_dir, test_name


def add_sample(index, test_dir, test_name, data):
    encoding = data['response']['encoding']
    filename = 'fixture%s.bin' % str(index)
    path = os.path.join(test_dir, filename)
    info = pickle_data({
        'data': pickle_data(data),
        'encoding': encoding,
        'fixture_version': FIXTURE_VERSION,
    })
    data = compress_data(info)
    with open(path, 'wb') as outfile:
        outfile.write(data)


# def clear_fixtures(base_path, spider_name):
#     path = os.path.join(base_path, "tests", spider_name)
#     shutil.rmtree(path, ignore_errors=True)


def compress_data(data):
    return zlib.compress(data)


def decompress_data(data):
    return zlib.decompress(data)


def pickle_data(data):
    return pickle.dumps(data, protocol=2)


def unpickle_data(data, encoding):
    if six.PY2:
        return pickle.loads(data)
    return pickle.loads(data, encoding=encoding)


def response_to_dict(response):
    return {
        'cls': '{}.{}'.format(
            type(response).__module__,
            getattr(type(response), '__qualname__', None) or getattr(type(response), '__name__', None)
        ),
        'url': response.url,
        'status': response.status,
        'body': response.body,
        'headers': dict(response.headers),
        'flags': response.flags,
        'encoding': response.encoding,
    }


def get_spider_class(spider_name, project_settings):
    spider_modules = project_settings.get('SPIDER_MODULES')
    for spider_module in spider_modules:
        modules = walk_modules(spider_module)
        for module in islice(modules, 1, None):
            for spider_class in iter_spider_classes(module):
                if spider_class.name == spider_name:
                    return spider_class
    return None


def parse_object(_object, spider, cb_settings):
    if isinstance(_object, Request):
        return parse_request(_object, spider, cb_settings)
    elif isinstance(_object, Response):
        return parse_object(response_to_dict(_object), spider, cb_settings)
    elif isinstance(_object, dict):
        for k, v in _object.items():
            _object[k] = parse_object(v, spider, cb_settings)
    elif isinstance(_object, (list, tuple)):
        if isinstance(_object, tuple):
            _object = list(_object)
        for i, v in enumerate(_object):
            _object[i] = parse_object(v, spider, cb_settings)
    return _object


# processes request for recording, handling auth settings
def parse_request(request, spider, cb_settings):
    _request = copy.deepcopy(request_to_dict(request, spider=spider))
    if not _request['callback']:
        _request['callback'] = 'parse'

    _clean_headers(_request['headers'], spider.settings, cb_settings)

    _meta = {}
    for key, value in _request.get('meta').items():
        if key != '_testmaster':
            _meta[key] = parse_object(value, spider, cb_settings)
    _clean_splash(_meta, spider.settings, cb_settings)
    _request['meta'] = _meta

    return _request


def _decode_dict(data):
    decoded = {}
    for key, value in data.items():
        if isinstance(key, bytes):
            key = key.decode()
        if isinstance(value, bytes):
            value = value.decode()
        if isinstance(value, list) and len(value) > 0:
            if isinstance(value[0], bytes):
                value = value[0].decode()
        decoded[key] = value
    return decoded


def _clean_splash(meta, spider_settings, cb_settings):
    splash_headers = meta.get('splash', {}).get('splash_headers', {})
    excluded_global = spider_settings.get(
        'TESTMASTER_EXCLUDED_HEADERS', default=[])
    try:
        excluded_local = cb_settings.EXCLUDED_HEADERS
    except AttributeError:
        excluded_local = []
    excluded = excluded_local if excluded_local else excluded_global

    included_global = spider_settings.get(
        'TESTMASTER_INCLUDED_AUTH_HEADERS', default=[])
    try:
        included_local = cb_settings.INCLUDED_AUTH_HEADERS
    except AttributeError:
        included_local = []
    included = included_local if included_local else included_global
    if 'Authorization' not in included or 'Authorization' in excluded:
        splash_headers.pop('Authorization', None)
    # deliberate inclusion!
    if 'Authorization' in splash_headers:
        try:
            splash_headers['Authorization'] = splash_headers['Authorization'].decode()
        except AttributeError:
            pass


def _process_for_json(data):
    def _is_jsonable(short_dict):
        try:
            json.dumps(short_dict)
            return True
        except:
            return False
    to_delete = []
    for k, v in data.items():
        if not _is_jsonable({k: v}):
            try:
                data[k] = str(v)
            except:
                to_delete.append(k)
    for d in to_delete:
        del data[d]


def _clean_headers(headers, spider_settings, cb_settings, mode=""):
    excluded_global = spider_settings.get('TESTMASTER_EXCLUDED_HEADERS', default=[])
    try:
        excluded_local = cb_settings.EXCLUDED_HEADERS
    except AttributeError:
        excluded_local = []
    excluded = excluded_local if excluded_local else excluded_global

    auth_headers = ['Authorization', 'Proxy-Authorization']
    included_global = spider_settings.get('TESTMASTER_INCLUDED_AUTH_HEADERS', default=[])
    try:
        included_local = cb_settings.INCLUDED_AUTH_HEADERS
    except AttributeError:
        included_local = []
    included = included_local if included_local else included_global

    excluded.extend([h for h in auth_headers if h not in included])
    for header in excluded:
        headers.pop(header, None)
        headers.pop(header.encode(), None)
    if mode == "decode":
        headers = _decode_dict(headers)
    return headers


# processes request into JSON format for inscribing in view.json and for validation
def clean_request(request, spider_settings, cb_settings):
    skipped_global = spider_settings.get('TESTMASTER_REQUEST_SKIPPED_FIELDS', default=[])
    try:
        skipped_local = cb_settings.REQUEST_SKIPPED_FIELDS
    except AttributeError:
        skipped_local = []
    skipped_fields = skipped_local if skipped_local else skipped_global
    _clean(request, skipped_fields)
    request = _decode_dict(request)
    request['headers'] = _clean_headers(request['headers'], spider_settings,
                                        cb_settings, mode="decode")
    _clean_splash(request['meta'], spider_settings, cb_settings)
    _process_for_json(request['meta'])
    return request


def clean_item(item, spider_settings, cb_settings):
    skipped_global = spider_settings.get('TESTMASTER_SKIPPED_FIELDS', default=[])
    try:
        skipped_local = cb_settings.SKIPPED_FIELDS
    except AttributeError:
        skipped_local = []
    skipped_fields = skipped_local if skipped_local else skipped_global

    _clean(item, skipped_fields)


def _clean(data, field_list):
    for field in field_list:
        data.pop(field, None)


def process_result(result, spider_settings, cb_settings):
    items = [copy.deepcopy(x["data"]) for x in filter(
        lambda res: res["type"] == "item", result)]
    requests = [copy.deepcopy(x["data"]) for x in filter(
        lambda res: res["type"] == "request", result)]
    for i in range(len(items)):
        clean_item(items[i], spider_settings, cb_settings)

    requests = [clean_request(req, spider_settings, cb_settings) for
                req in requests]
    return items, requests


def erase_special_metakeys(request):
    new_meta = {}
    for k, v in request.meta.items():
        if not k.startswith('_'):
            new_meta[k] = v
    new_req = request.replace(meta=new_meta)
    return new_req


def write_test(path, test_name, url):
    command = 'scrapy {}'.format(' '.join(sys.argv))
    test_path = os.path.join(path, 'test_fixtures.py')
    config_file = os.path.join(path, 'config.py')

    test_code = '''# THIS IS A GENERATED FILE
# Generated by: {command}  # noqa: E501
# Request URL: {url}  # noqa: E501
import os
import unittest
from scrapy_testmaster.utils import generate_test


class TestMaster(unittest.TestCase):
    def test__{test_name}(self):
        files = os.listdir(
            os.path.dirname(
                os.path.abspath(__file__)
            )
        )
        files = [f for f in files if f.endswith('.bin')]
        self.maxDiff = None
        for f in files:
            file_path = os.path.join(os.path.dirname(__file__), f)
            print("Testing fixture '%s' in location: %s" % (f, file_path))
            test = generate_test(os.path.abspath(file_path))
            test(self)


if __name__ == '__main__':
    unittest.main()
'''.format(
        test_name=test_name,
        command=command,
        url=url,
    )

    with open(str(test_path), 'w') as f:
        f.write(test_code)

    if not os.path.exists(config_file):
        config_src = os.path.dirname(__file__) + '/config_doc.py'
        shutil.copyfile(config_src, config_file)


def binary_check(fx_obj, cb_obj, encoding):
    if isinstance(cb_obj, (dict, Item)):
        fx_obj = {
            key: binary_check(value, cb_obj[key], encoding)
            for key, value in fx_obj.items()
        }

    if isinstance(cb_obj, list):
        fx_obj = [
            binary_check(fxitem, cbitem, encoding)
            for fxitem, cbitem in zip(fx_obj, cb_obj)
        ]

    if isinstance(cb_obj, Request):
        headers = {}
        for key, value in fx_obj['headers'].items():
            key = to_bytes(key, encoding)
            headers[key] = [to_bytes(v, encoding) for v in value]
        fx_obj['headers'] = headers
        fx_obj['body'] = to_bytes(fx_obj['body'], encoding)

    if isinstance(cb_obj, six.binary_type):
        fx_obj = fx_obj.encode(encoding)

    return fx_obj


def set_spider_attrs(spider, _args):
    for k, v in _args.items():
        setattr(spider, k, v)


def parse_callback_result(result, spider, cb_settings):
    processed_result = []
    out = []
    for elem in result:
        out.append(elem)
        is_request = isinstance(elem, Request)
        if is_request:
            _data = parse_request(elem, spider, cb_settings)
        else:
            _data = parse_object(copy.deepcopy(elem), spider, cb_settings)
        processed_result.append({
            'type': 'request' if is_request else 'item',
            'data': _data
        })
    return processed_result, out


def prepare_callback_replay(fixture_path, encoding="utf-8"):
    with open(str(fixture_path), 'rb') as f:
        raw_data = f.read()

    fixture_info = unpickle_data(decompress_data(raw_data), encoding)
    if 'fixture_version' in fixture_info:
        encoding = fixture_info['encoding']
        data = unpickle_data(fixture_info['data'], encoding)
    else:
        data = fixture_info  # legacy tests

    settings = get_project_settings()

    spider_name = data.get('spider_name')
    if not spider_name:  # legacy tests
        spider_name = os.path.basename(
            os.path.dirname(
                os.path.dirname(fixture_path)
            )
        )

    spider_cls = get_spider_class(spider_name, settings)
    spider_cls.update_settings(settings)

    for k, v in data.get('settings', {}).items():
        settings.set(k, v, 50)

    crawler = Crawler(spider_cls, settings)
    spider_args_in = data.get('spider_args', data.get('spider_args_in', {}))
    spider = spider_cls.from_crawler(crawler)
    for k, v in spider_args_in.items():
        setattr(spider, k, v)
    crawler.spider = spider

    return data, crawler, spider, settings


def generate_test(fixture_path, encoding='utf-8'):
    data, crawler, spider, settings = prepare_callback_replay(
        fixture_path, encoding=encoding
    )

    def test(self):
        fx_result = data['result']
        fx_version = data.get('python_version')

        spider_args_in = data.get(
            'spider_args', data.get('spider_args_in', {}))
        set_spider_attrs(spider, spider_args_in)
        request = request_from_dict(data['request'], spider)
        response_cls = auto_import(data['response'].pop(
            'cls', 'scrapy.http.HtmlResponse'))
        response = response_cls(request=request, **data['response'])

        middlewares = []
        middleware_paths = data['middlewares']
        for mw_path in middleware_paths:
            try:
                mw_cls = load_object(mw_path)
                mw = create_instance(mw_cls, settings, crawler)
                middlewares.append(mw)
            except NotConfigured:
                continue

        crawler.signals.send_catch_log(
            signal=signals.spider_opened,
            spider=spider
        )
        result_attr_in = {
            k: v for k, v in spider.__dict__.items()
            if k not in ('crawler', 'settings', 'start_urls')
        }
        if not settings.getbool("TESTMASTER_IGNORE_SPIDER_ARGS"):
            self.assertEqual(spider_args_in, result_attr_in,
                             'Input arguments not equal!\nFixture path: %s' % fixture_path)

        for mw in middlewares:
            if hasattr(mw, 'process_spider_input'):
                mw.process_spider_input(response, spider)

        result = arg_to_iter(request.callback(response))
        middlewares.reverse()

        for mw in middlewares:
            if hasattr(mw, 'process_spider_output'):
                result = mw.process_spider_output(response, result, spider)

        for index, (cb_obj, fx_item) in enumerate(six.moves.zip_longest(
            result, fx_result, fillvalue=NO_ITEM_MARKER
        )):
            if any(item == NO_ITEM_MARKER for item in (cb_obj, fx_item)):
                raise AssertionError(
                    "The fixture's data length doesn't match with "
                    "the current callback's output length. "
                    "Expected %s elements, found %s.\nFixture path: %s" % (
                        len(fx_result), index + 1 + len(list(result)),
                        fixture_path)
                )

            test_dir = '/'.join(fixture_path.split('/')[:-1])
            cb_settings = get_cb_settings(test_dir)

            cb_obj = parse_object(cb_obj, spider, cb_settings)

            fx_obj = fx_item['data']
            if fx_item['type'] == 'request':
                fx_obj = clean_request(fx_obj, settings, cb_settings)
                cb_obj = clean_request(cb_obj, settings, cb_settings)
                try:
                    validate_results(test_dir, settings, [], [cb_obj], request.url)
                except _InvalidOutput as e:
                    six.raise_from(
                        _InvalidOutput(
                            "Callback output #{} is invalid "
                            "Problem: {}.\nFixture path: {}".format(index, e, fixture_path)),
                        None)
            else:
                clean_item(fx_obj, settings, cb_settings)
                clean_item(cb_obj, settings, cb_settings)
                try:
                    validate_results(fixture_path, settings, [cb_obj], [], request.url)
                except _InvalidOutput as e:
                    six.raise_from(
                        _InvalidOutput(
                            "Callback output #{} is invalid "
                            "Problem: {}.\nFixture path: {}".format(index, e, fixture_path)),
                        None)

            if fx_version == 2 and six.PY3:
                fx_obj = binary_check(fx_obj, cb_obj, encoding)

            try:
                datadiff.tools.assert_equal(fx_obj, cb_obj)
            except AssertionError as e:
                six.raise_from(
                    AssertionError(
                        "Callback output #{} doesn't match recorded "
                        "output: {}.\nFixture path: {}".format(index, e, fixture_path)),
                    None)

        # Spider attributes get updated after the yield
        result_attr_out = {
            k: v for k, v in spider.__dict__.items()
            if k not in ('crawler', 'settings', 'start_urls')
        }

        if not settings.getbool("TESTMASTER_IGNORE_SPIDER_ARGS"):
            self.assertEqual(data['spider_args_out'], result_attr_out,
                             'Output arguments not equal!\nFixture path: %s' % fixture_path)
    return test
