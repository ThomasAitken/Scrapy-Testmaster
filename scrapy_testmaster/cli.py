import re
import os
import sys
import json
import scrapy
import argparse
from glob import glob
from datetime import datetime
from w3lib.url import is_url

from scrapy.crawler import CrawlerProcess
from scrapy.utils.python import to_unicode
from scrapy.utils.reqser import request_from_dict
from scrapy.utils.project import inside_project, get_project_settings
from scrapy.commands.genspider import sanitize_module_name
from scrapy.exceptions import UsageError

from scrapy_testmaster.utils import (
    add_sample,
    auto_import,
    unpickle_data,
    decompress_data,
    get_project_dir,
    parse_callback_result,
    prepare_callback_replay,
    get_or_create_test_dir
)
from scrapy_testmaster.utils_novel import (
    get_callbacks,
    get_cb_settings,
    get_test_paths,
    write_config,
    get_homepage_cookies,
    trigger_requests,
    get_reqs_to_add,
    get_reqs_multiple,
    validate_results
)
from .parse import (
    process_options,
    run_command
)



class CommandLine:
    def __init__(self, parser):
        self.parser = parser
        self.args = parser.parse_args()

        if not inside_project():
            self.error("No active Scrapy project")

        self.command = self.args.command

        self.spider = sanitize_module_name(self.args.spider) if \
            self.args.spider else None 
        try:
            self.callback = self.args.callback
        except AttributeError:
            self.callback = None
        try:
            self.fixture = self.args.fixture
        except AttributeError:
            self.fixture = None
            
        if self.command == 'update':
            try:
                self.new = self.args.new
            except AttributeError:
                self.new = None
            try:
                self.dynamic = self.args.dynamic
            except AttributeError:
                self.dynamic = None

        if self.fixture and not self.callback:
            self.error("Can't specify a fixture without a callback")

        self.project_dir = get_project_dir()
        sys.path.append(self.project_dir)

        self.settings = get_project_settings()

        if self.command == "parse":
            url_list = [url.strip() for url in self.args.urls.split(',')]
            for url in url_list:
                if not is_url(url):
                    self.error("Something went wrong with your urls arg!")

            self.args = process_options(self.args)
            crawler_process = CrawlerProcess(self.settings)
            run_command(crawler_process, url_list, self.args)

        else:
            self.base_path = self.settings.get(
                'TESTMASTER_BASE_PATH',
                default=os.path.join(self.project_dir, 'testmaster'))
            self.tests_dir = os.path.join(self.base_path, 'tests')

            self.spider_dir = os.path.join(self.tests_dir, self.spider)

            if not os.path.isdir(self.spider_dir) and self.command != "establish":
                self.error(
                    "No recorded data found "
                    "for spider '{}'".format(self.spider))

            self.extra_path = self.settings.get('TESTMASTER_EXTRA_PATH') or ''
            if self.callback:
                self.callback_dir = os.path.join(
                    self.spider_dir, self.extra_path, self.callback)

                if self.command == 'establish':
                    if os.path.isdir(self.callback_dir):
                        self.error(
                            "Can't use 'establish' with callback arg "
                            "if callback dir for spider '{}' "
                            "exists already".format(self.spider))
            else:
                if self.command == 'inspect':
                    self.error(
                        "No recorded data found for callback "
                        "'{}' from '{}' spider".format(self.callback, self.spider))

            if self.fixture:
                self.fixture_path = os.path.join(
                    self.callback_dir, self.parse_fixture_arg())
                if not os.path.isfile(self.fixture_path):
                    self.error("Fixture '{}' not found".format(self.fixture_path))

    def error(self, msg):
        print(msg)
        sys.exit(1)

    def parse_fixture_arg(self):
        try:
            int(self.fixture)
            return 'fixture{}.bin'.format(self.fixture)
        except ValueError:
            pass
        if not self.fixture.endswith('.bin'):
            return '{}.bin'.format(self.fixture)
        return self.fixture

    def parse_data(self, data):
        if isinstance(data, (dict, scrapy.Item)):
            return {
                self.parse_data(k): self.parse_data(v)
                for k, v in data.items()
            }
        elif isinstance(data, list):
            return [self.parse_data(x) for x in data]
        elif isinstance(data, bytes):
            return to_unicode(data)
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, (int, float)):
            return data
        return str(data)

    def get_fixture_data(self):
        with open(self.fixture_path, 'rb') as f:
            raw_data = f.read()
        fixture_info = unpickle_data(decompress_data(raw_data), 'utf-8')
        if 'fixture_version' in fixture_info:
            encoding = fixture_info['encoding']
            data = unpickle_data(fixture_info['data'], encoding)
        else:
            data = fixture_info  # legacy tests (not all will work, just utf-8)
        return data

    def inspect(self):
        data = self.parse_data(self.get_fixture_data())
        print(json.dumps(data))

    def update(self):
        to_update = []
        if self.fixture:
            to_update.append(self.fixture_path)
        elif not self.fixture and self.callback:
            target = os.path.join(self.callback_dir, "*.bin")
            to_update = glob(target)
        # == if not self.callback
        else:
            spider_path = os.path.join(self.project_dir, \
                os.path.join(os.path.basename(self.project_dir), 'spiders/' + \
                self.spider + '.py'))
            to_update = get_test_paths(self.spider_dir, spider_path, self.extra_path, True)

        req_list = []
    
        homepage_cookies = {}
        i = 0
        for path in to_update:
            data, _, spider, _ = prepare_callback_replay(path)
            if (self.dynamic or self.new) and i == 0:
                homepage_cookies = get_homepage_cookies(spider)
                i += 1

            request = request_from_dict(data['request'], spider)
            if homepage_cookies:
                request.cookies = homepage_cookies
            fixture_dir, filename = os.path.split(path)
            fixture_index = re.search(r"\d+", filename).group()
            if self.dynamic:
                request.meta['_update'] = 1
                request.meta['_fixture'] = fixture_index
                req_list.append(request)
            else:
                response_cls = auto_import(
                    data['response'].pop('cls', 'scrapy.http.HtmlResponse')
                )
                response = response_cls(
                    request=request, **data['response'])

                cb_settings = get_cb_settings(fixture_dir)
                data["result"], _ = parse_callback_result(
                    request.callback(response), spider, cb_settings
                )
                validate_results(fixture_dir, spider.settings, data['result'], data['request']['url'])
                add_sample(fixture_index, fixture_dir, filename, data)

                print("Fixture '{}' successfully updated.".format(
                    os.path.relpath(path)))
        if self.dynamic or self.new:
            crawler_process = CrawlerProcess(self.settings)
            if self.callback:
                # add any requests specified in REQUESTS_TO_ADD in config.py
                req_list += get_reqs_to_add(self.callback_dir, spider)
                trigger_requests(crawler_process, spider, req_list)
            else:
                # finds all paths to all config.py files for the spider
                # potentially adding a whole lot of requests from the REQUESTS_TO_ADD fields in these
                to_add = get_test_paths(self.spider_dir, spider_path, self.extra_path)
                req_list += get_reqs_multiple(to_add, spider)
                trigger_requests(crawler_process, spider, req_list)
                

    def establish(self):
        did_something = False
        if self.callback:
            if not os.path.exists(self.callback_dir):
                get_or_create_test_dir(self.base_path, self.spider, self.callback, self.extra_path)
                write_config(self.callback_dir)
                did_something = True
        else:
            spider_path = os.path.join(self.project_dir, \
                os.path.join(os.path.basename(self.project_dir), 'spiders/' + \
                self.spider + '.py'))
            for callback in get_callbacks(spider_path):
                callback_dir = os.path.join(
                    self.spider_dir, self.extra_path, callback)
                cb_exists = False
                if os.path.exists(callback_dir):
                    cb_exists = True
                get_or_create_test_dir(self.base_path, self.spider, callback, self.extra_path)
                if not cb_exists:
                    write_config(callback_dir)
                    did_something = True
        if did_something:
            print("Command successful! Now you can tweak callback-specific "
                "settings in the config.py file/s generated.")
        else:
            print("Command did nothing because a dir exists for callback/s "
                "indicated already.")


    def parse_command(self):
        if self.command == "inspect":
            self.inspect()
        elif self.command == "update":
            self.update()
        elif self.command == "establish":
            self.establish()


def main():
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(help='Action commands', dest='command')
    subparsers.required = True

    parse_cmd = subparsers.add_parser(
        'parse',
        description="Downloads and parses n requests up to depth d with different "
            "urls but the same attributes otherwise",
        formatter_class=argparse.RawTextHelpFormatter)
    parse_cmd.add_argument("urls", help="urls separated by a comma")
    parse_cmd.add_argument("--spider", dest="spider",
        help="use this spider without looking for one")
    parse_cmd.add_argument("-a", dest="spargs", action="append", default=[], metavar="NAME=VALUE",
        help="set spider argument (may be repeated)")
    parse_cmd.add_argument("--homepage", dest="homepage", action="store_true",  
        help="choose whether to get cookies from homepage")
    parse_cmd.add_argument("--pipelines", action="store_true",
        help="process items through pipelines")
    parse_cmd.add_argument("--nolinks", dest="nolinks", action="store_true",
        help="don't show links to follow (extracted requests)")
    parse_cmd.add_argument("--noitems", dest="noitems", action="store_true",
        help="don't show scraped items")
    parse_cmd.add_argument("--nocolour", dest="nocolour", action="store_true",
        help="avoid using pygments to colorize the output")
    parse_cmd.add_argument("-r", "--rules", dest="rules", action="store_true",
        help="use CrawlSpider rules to discover the callback")
    parse_cmd.add_argument("-c", "--callback", dest="callback",
        help="use this callback for parsing, instead looking for a callback")
    parse_cmd.add_argument("-m", "--meta", dest="meta",
        help="inject extra meta into the Request, it must be a valid raw json string")
    parse_cmd.add_argument("--cbkwargs", dest="cbkwargs",
        help="inject extra callback kwargs into the Request, it must be a valid raw json string")
    parse_cmd.add_argument("-d", "--depth", dest="depth", type=int, default=1,
        help="maximum depth for parsing requests [default: %default]")
    parse_cmd.add_argument("-v", "--verbose", dest="verbose", action="store_true",
        help="print each depth level one by one")
    parse_cmd.add_argument("--headers", dest="headers", 
        help="inject extra headers, it must be a valid raw json string")
    parse_cmd.add_argument("--method", dest="method", 
        help="specify \'post\' to get a POST request")
    parse_cmd.add_argument("--cookies", dest="cookies", 
        help="add cookies to send, it must be a raw json string")


    inspect_cmd = subparsers.add_parser(
        'inspect',
        description="Inspects fixtures data returning a JSON object",
        formatter_class=argparse.RawTextHelpFormatter)
    inspect_cmd.add_argument('spider', help="The spider to update.")
    inspect_cmd.add_argument('callback', help="The callback to update.")
    inspect_cmd.add_argument('fixture', help=(
        "The fixture to update.\n"
        "Can be the fixture number or the fixture name."))

    update_cmd = subparsers.add_parser(
        'update',
        description="Updates fixtures to callback changes",
        formatter_class=argparse.RawTextHelpFormatter)
    update_cmd.add_argument('spider', help="The spider to update.")
    update_cmd.add_argument('-c', '--callback', help="The callback to update.")
    update_cmd.add_argument('-f', '--fixture', help=(
        "The fixture to update.\n"
        "Can be the fixture number or the fixture name.\n"
        "If not specified, all fixtures will be updated."))
    update_cmd.add_argument('--dynamic', action="store_true", 
        help=("Include this to re-download the response."))
    update_cmd.add_argument('--new', action="store_true",
        help=("Downloads requests from REQUESTS_TO_ADD"))


    establish_cmd = subparsers.add_parser(
        'establish',
        description="Sets up test structure without requiring any requests to be made.",
        formatter_class=argparse.RawTextHelpFormatter)
    establish_cmd.add_argument('spider', help=(
        "The spider for which to set up the test environment.\n"
        "If no spider specified, nothing will happen.\n"
        "If no callback after this, then a directory is created for all callbacks."))
    establish_cmd.add_argument('-c', '--callback', help=(
        "The callback for which to set up the test structure.\n"
        "If not preceded by a spider, this will fail.\n"))

    cli = CommandLine(parser)
    cli.parse_command()
