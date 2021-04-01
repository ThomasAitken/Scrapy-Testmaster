
# Scrapy TestMaster

[![PyPI Version](https://img.shields.io/pypi/v/scrapy-testmaster.svg?color=blue)](https://pypi.org/project/scrapy-testmaster)
[![GitHub Actions (Tests)](https://github.com/ThomasAitken/Scrapy-Testmaster/workflows/Tests/badge.svg)](https://github.com/ThomasAitken/Scrapy-Testmaster/)

## Overview

Scrapy TestMaster is an automatic test-generation, test-execution and general debugging tool for Scrapy spiders.

As far as I am aware, Scrapy TestMaster is the most comprehensive tool yet for the automated debugging and testing of Scrapy spiders. It represents a strict extension of the capabilities of its most influential predecessor, Scrapy Autounit (https://github.com/scrapinghub/scrapy-autounit), with further features that make it more useful for both on-the-fly debugging and more robust monitoring of the kind that might be required in an enterprise context. Whereas other Scrapy testing libraries are useful only for crawler-validation subsequent to changes in the crawler code, this library offers further tools to test for changes in the targeted webpages themselves. More precisely, its capabilities include the following: 
- Testing your Scrapy functions against specific requests on the fly, using an extended version of the Scrapy parse command (https://docs.scrapy.org/en/latest/topics/commands.html#std-command-parse) that can take any number of urls ([*testmaster parse*](#testmaster-parse)).
- Using the above command to automatically generate testcases and unit tests.
- Generating automatic testcases and unit tests as you run your spider via `scrapy crawl`.
- Merging the debugging and test-generation processes by designing meta rules to determine whether a fixture (testcase) should be written based on the quality of the parsed results.
- Specifying requests in a config file to be downloaded and evaluated upon the next execution (allows FormRequests, requests with cookies, requests using proxies, etc).
- Designing custom testing/validation rules down to a callback-specific level so as to check the correctness of output in a very fine-grained manner.
- Updating and validation of existing tests via a re-parsing of the original HTML source with the current spider code.
- Updating and validation of existing tests via an additional re-downloading of the HTML source using the same request.

Apart from the wider range of capabilities, the feature I most want to emphasise about this library is that it gives you the ability to *synthesise the processes of debugging and testcase-generation*. First you set up the custom logic for validating the output of your spider/s, then you call `scrapy crawl` or `testmaster parse`. If the results are acceptable, testcases are written; otherwise, you get an informative error message. 

For more info on how to use this library, see [*What is the Use Case for this Library*](#What-is-the-Use-Case-for-this-Library).  

---  
## Acknowledgements
The structure of my project was strongly influenced by Scrapy Autounit. The `scrapy parse` command is, of course, another major influence, the code for which bears a very strong resemblance to `testmaster parse`. Read the License for more.  

---
## Installation
```
pip install scrapy-testmaster
```

---
## What it looks like
This is what your project will look like after calling `scrapy crawl` or `testmaster parse` with TestMasterMiddleware enabled.
```
my_project

├── my_project
│   ├── __init__.py
│   ├── items.py
│   ├── middlewares.py
│   ├── pipelines.py
│   ├── settings.py
│   └── spiders
│       ├── __init__.py
│       └── my_spider.py
├── testmaster
│   ├── __init__.py
│   └── tests
│       ├── __init__.py
│       └── my_spider
│           ├── __init__.py
│           └── my_callback
│               ├── __init__.py
│               ├── config.py
│               ├── fixture1.bin
│               ├── fixture2.bin
│               ├── test_fixtures.py
│               ├── view.json 
└── scrapy.cfg
```

Analogous to the `settings.py` module in every Scrapy project, `config.py` is for specifying the custom logic and rules that your test-results need to pass for the given callback directory in which the file resides. It also allows one to write down requests to be tested the next time you execute `testmaster parse`. `view.json` is simply a convenience for representing what's currently in your fixtures: it is an ordered list of the requests that generated the current fixtures for the callback in question, plus some basic summary stats. It is updated if the fixtures are changed. 

I'm considering changing this structure so that the `testmaster` folder is eliminated and the `tests` folder is placed within the `my_project` subfolder (the folder containing `settings.py` and `spiders` which can have a different name from the outer folder). 

---
## Usage
### Basic
To begin validating output or generating tests with `testmaster parse` or `scrapy crawl`, set `TESTMASTER_ENABLED = True` in `settings.py`, then add the spider middleware to your `SPIDER_MIDDLEWARES` setting (no specific order required):  
```python
SPIDER_MIDDLEWARES = {
    'scrapy_testmaster.TestMasterMiddleware': 950
}
```

### Generating tests
Make sure you enable Scrapy Testmaster in your settings:
```python
TESTMASTER_ENABLED = True
```
To generate your fixtures, you have three basic options:
1. Scrapy Testmaster will generate them for you while running your spider as usual. 
```
$ scrapy crawl my_spider
```
2. Automatically generate testcases for specified urls against a specified callback using `testmaster parse`, an extended version of the Scrapy `parse` command chiefly distinguished by its permission of multi-url inputs.
```
$ testmaster parse "url1|url2|url3" --spider=my_spider -c my_callback --meta='{"x":"y"}' ...
```
3. Specify requests to be later executed in python-dict format within the `config.py` file for the spider and callback in question (e.g. `"url":"", "headers":{..}, "_class":"scrapy.http.request.form.FormRequest"`}). These will get executed whenever you call `testmaster update` with the appropriate spider, callback args and options (see [`testmaster update`](#testmaster-update)), and lead to new fixtures being written subject to the usual conditions.
```
$ testmaster update my_spider -c my_callback --new
```

The first two of these commands will automatically generate a directory `testmaster` in your project root dir if none exists, containing all the generated tests/fixtures for the spider you just ran, plus two more files (`config.py` and `view.json`). (See the directory tree example above.) 

### Other specific tasks

###### Setting up testing environment for given spider/callback before making any requests
```
$ testmaster establish my_spider -c my_callback
```
(If no callback is specified, every single callback in the spider will get its own directory with a `config.py` file.)
###### Generating new tests for specific urls on the fly
```
$ testmaster parse "url1|url2|url3|..." --spider=my_spider -c my_callback --meta='{"x":"y"}' ...
```
###### Testing output against custom rules on the fly
First, set up your rules in the appropriate `config.py` file, then run:
```
$ testmaster parse "url1|url2|url3|..." --spider=my_spider -c my_callback --meta='{"x":"y"}' ...
```
If the results generated by such a command are all fine according to your custom rules, the fixtures/tests will be written (assuming you haven't reached the fixtures cap you set). Otherwise, you will get an error message about the failure mode. This is an example of how you can merge the debugging and test-generation processes.
###### Updating the results of tests in response to changes in spider code (i.e. re-parsing the downloaded source within the fixture)
```
$ testmaster update my_spider -c my_callback --fixture n
```
(If no fixture is specified, every fixture is changed.)
###### Remaking the entire fixture using the original request to check for a website change (i.e. re-downloading the response)
```
$ testmaster update my_spider -c my_callback --dynamic
```
###### Triggering the download of complex requests (e.g. FormRequests) described in a config.py file
Define a request in Python-dict within a config.py file for the relevant callback, and then call:
```
$ testmaster update my_spider -c my_callback --new
```
If the results of the request triggered by this command pass your custom rules, and there is space in the fixtures, a new fixture will be written for this request and response.  
###### Clearing some fixtures that are surplus to requirements (and re-ordering the rest within the directory)
```
$ testmaster clear my_spider my_callback 1,4,8,10
```

### Running tests
To run your tests statically, you can use `unittest` regular commands.

###### Test all
```
$ python -m unittest
```
###### Test a specific spider
```
$ python -m unittest discover -s testmaster.tests.my_spider
```
###### Test a specific callback
```
$ python -m unittest discover -s testmaster.tests.my_spider.my_callback
```
###### Test a specific fixture
```
$ python -m unittest testmaster.tests.my_spider.my_callback.test_fixture2
```

It's worth stating that all of the commands in this library apart from `establish`, `inspect` and `clear` have a debugging/testing purpose. These `unittest` commands are just useful to test your code against existing fixtures without changing them in any way.

### Important Caveats
* As long as **TESTMASTER_ENABLED** is on, each time you run a spider using `scrapy crawl`, existing tests/fixtures will be over-written, if the results of the requests being made pass your custom rules. However, if you run a specific callback using `testmaster parse`, this over-writing will not apply - fixtures will be added (within the limit you have set by **TESTMASTER_MAX_FIXTURES_PER_CALLBACK**).
* There are a few lines of code in this library that rely on the assumption that you haven't named your spider file differently from the name attribute of the spider itself. So keep these names aligned if you want assurance that everything will always work! (If you always use `scrapy genspider` and don't later edit the file name or spider name, there will, of course, be no problem.)
* Running the *scrapy parse* command (as opposed to the *testmaster parse* command) with the TestMasterMiddleware enabled will not work properly - the middleware will try and fail to interact with the responses.
* This package works best with base Scrapy spiders, rather than e.g. CrawlSpiders or SiteMapSpiders, at least when running `scrapy crawl` (as opposed to using `testmaster parse` and sending the results to one of the explicitly written callbacks in your spider code). For example, in the case of CrawlSpiders, it will write folders for callbacks called `_callback` and `_parse_response` (the underlying callbacks of the CrawlSpider code). I might try to alter this if there is demand. 
* Just in case this happens to be relevant, using as keys in your request.meta any of the strings '_parse', '_update' or '_fixture' may lead to unexpected behaviour with the middleware enabled.  

### What's the deal with the fixtures?
The fixtures are essentially just test cases for your spider. The *fixture%d.bin* files store in binary format a big JSON dict containing the spider name that generated the fixture, the full details of the request, the entire downloaded response body, the result (i.e. a list of items and/or requests corresponding to the generator produced by the callback code), details about the middlewares in play, the spider settings, the spider args, and the Python version. This library offers you two ways of using these fixtures to run your tests, once they've been written: 
1. Run a static test which parses the response using your updated code for the same callback (to check that you have not broken anything by comparing against the results in the fixture).
2. Run a dynamic test which first downloads a new response using the request info encoded in the fixture, and then parses the response using your code for the callback (to check that the website has not changed).  

---
### Project/Spider Settings
#### N.B. 
You will notice that there is heavy overlap here with the settings in config.py. So you can set custom validation rules at any level, although any settings specified to a contrary, non-default value in a `config.py` file will take precedence for that particular callback.  

**TESTMASTER_ENABLED**  
Set this to `True` or `False` to enable or disable unit test generation when calling `scrapy crawl`, `testmaster parse` or when running `testmaster update` with the `--dynamic` or `--new` options. The other commands are completely unaffected (e.g. you can run static updates with or without this enabled).

**TESTMASTER_MAX_FIXTURES_PER_CALLBACK**  
Sets the maximum number of fixtures to store per callback.  
`Minimum: 10`  
`Default: 10`

**TESTMASTER_SKIPPED_FIELDS**  
Sets a list of fields to be skipped from testing your callbacks' items. It's useful to bypass fields that return a different value on each run.  
For example if you have a field that is always set to `datetime.now()` in your spider, you probably want to add that field to this list to be skipped on tests. Otherwise you'll get a different value when you're generating your fixtures than when you're running your tests, making your tests fail.  
`Default: []`

**TESTMASTER_REQUEST_SKIPPED_FIELDS**  
Sets a list of request fields to be skipped when running your tests.  
Similar to TESTMASTER_SKIPPED_FIELDS but applied to requests instead of items.  
`Default: []`

**TESTMASTER_EXCLUDED_HEADERS**  
Sets a list of headers to exclude from requests recording.  
For security reasons, Testmaster already excludes `Authorization` and `Proxy-Authorization` headers by default, if you want to include them in your fixtures and `view.json` see *`TESTMASTER_INCLUDED_AUTH_HEADERS`*.  
`Default: []`  

**TESTMASTER_INCLUDED_AUTH_HEADERS**  
If you want to include `Authorization` or `Proxy-Authorization` headers in your fixtures and `view.json`, add one or both of them to this list. 
This also applies to a Scrapy-Splash API key which would normally reside in `splash_headers` under the `Authorization` key. Put 'Authorization' in this list to include such a key.
`Default: []`

**TESTMASTER_INCLUDED_SETTINGS**  
Sets a list of settings names to be recorded in the generated test case.  
`Default: []`

**TESTMASTER_EXTRA_PATH**  
This is an extra string element to add to the test path and name between the spider name and callback name. You can use this to separate tests from the same spider with different configurations. This is respected by all methods of creating directories for spiders + callbacks, i.e. `testmaster establish`, `testmaster parse` and `scrapy crawl`.   It is also respected by `testmaster update` when it's working out what fixtures you want to update.  
`Default: None`  

The following 3 settings are the main way to implement custom testing behaviour. They have two utilities: *ex-ante* and *ex-post*. **ex-ante**: if the rules established by these settings are violated while Testmaster is evaluating the results of a request that has not yet become a fixture, the fixture will not be written. **ex-post**: if any of them are violated when you're updating an existing fixture (i.e. parsing the pre-downloaded response with new code), you know that you have made a bad change to your code. 

**TESTMASTER_OBLIGATE_ITEM_FIELDS**  
Insert here any field names which you intend to exist in every "item" (as opposed to "request") object outputted by the tests within this project. 
You can set this to a non-default value but override for specific spiders + callbacks by tweaking the corresponding field in the relevant local config.py file/s.  
`Default: []`

**TESTMASTER_PRIMARY_ITEM_FIELDS**  
Insert here any field names which you intend to be non-empty in every "item" object outputted by the tests within this project.
It is not necessary to duplicate a field name across this and the above setting; just put the field in this list.
You can set this to a non-default value but override for specific spiders + callbacks by tweaking the corresponding field in the relevant local config.py file/s.   
`Default: []`

**TESTMASTER_PATH_TO_RULES_FILE**  
Insert here a relative path (relative from the project root, minus ".py" extension) to a Python file containing at least one of the following two classes: `class RequestRules(object)` and `class ItemRules(object)`. Within these classes, you can devise any number of functions, given whatever names you like, that take one changeable argument each: a "request" in the former case and an "item" in the latter. These functions are intended to contain one or more "assertion" statements.  
All items will be tested against your item rules, and equivalently for requests.  
`Default: None`  

**Note**: Remember that you can always apply any of these settings per spider including them in your spider's `custom_settings` class attribute - see https://docs.scrapy.org/en/latest/topics/settings.html#settings-per-spider.  
<br/>

### Callback-specific settings (in config.py)
Be apprised that any list-type options are not combined across the global value and the equivalent local value in the config.py file. That is to say, if you want to add one more element to one of these options like ...EXCLUDED_HEADERS or ...INCLUDED_SETTINGS at the callback level, you can't just fill the list in the config.py file with that single additional element; you must include all of the elements. (This already follows from the rule I stated earlier and which I'll restate again: if any edits away from the default have been made at the local level for a given setting, those edits dominate.) As for custom rules, they work as follows: the global custom rules are tried after the local rules are tried. So you can't override the global custom rules with the local rules.

**MAX_FIXTURES**  
Equivalent to global setting.

**SKIPPED_FIELDS**  
Equivalent to global setting.

**REQUEST_SKIPPED_FIELDS**   
Equivalent to global setting.

**EXCLUDED_HEADERS**   
Equivalent to global setting.

**INCLUDED_AUTH_HEADERS**  
Equivalent to global setting.

**INCLUDED_SETTINGS**  
Equivalent to global setting.

**OBLIGATE_ITEM_FIELDS**  
Equivalent to global setting.

**PRIMARY_ITEM_FIELDS**  
Equivalent to global setting.

**REQUESTS_TO_ADD**  
This is for storing complex requests in Python dict format that will be executed the next time you run any command of `testmaster update` with args indicating the relevant callback, and using either of the options `--dynamic` or `--new` (see [`testmaster update`](#testmaster-update)). It allows you to use all the standard request args as keys plus the "_class" key for specifying a FormRequest or a SplashRequest. The motivation behind it is the difficulty/impossibility involved in trying to do the same thing for special/complex requests using `testmaster parse` on the command-line. Obviously, you can also specify simple requests here if you like.  
Example of request format with special requests:
```
[
    {
        "url": "https://examplewebsite011235811.com/info",  
        "headers": {"referer":"...", "content_type": "..."},
        "method": "POST",
        "_class": "scrapy.http.request.form.FormRequest",
        "body": "user=blah&password=blah",
        "meta": {"x": "y"}
    },
    {
    	"url": "https://...-splash.scrapinghub.com/render.html", 
	"method": "POST", 
	"headers": {...}, 
	"body": "{...}", 
	"meta": {"splash": {"endpoint": "render.html", "splash_headers": {'Authorization': INSERT_API_KEY}, "args": {"url": "..."}}},
	"dont_filter": false,
	"_class": "scrapy_splash.request.SplashRequest"
    }
]
```
`Default: []`  
All of these keys are optional except "url" and "meta". The callback is inferred from the location of the config.py file. You can get a sense of what the format for a given request needs to look like by running `scrapy crawl` for that spider and looking at `view.json` for the relevant callback. The only caveat is that JSON "nulls" need to be converted to Python "None", and same for JSON "true"/"false" (to "True"/"False").  
When this request is triggered, it is treated as if you had run `testmaster parse` with the same info. So its response and results can then become part of a new fixture if all your validation rules are passed and there is space.

Currently, you're going to have to delete these requests manually from the `config.py` file after they've been added to make sure they're not triggered again next time you execute `testmaster update`.

**Other**  
All config.py files will include by default two classes: `class ItemRules(object)` and `class RequestRules(object)`. You can define any number of methods for these classes that take args {*self*, *item*} and {*self*, *request*} respectively. The logic for such methods was explained previously in the precis for **TESTMASTER_PATH_TO_RULES_FILE**.  

### Format of view.json  
```
{"1": {"request": {"url": "...", "callback": "...", "errback": null, "method": "GET", "headers": {...}, "body": "", 
"cookies": {}, "meta": {...}, "_encoding": "utf-8", "priority": 0, "dont_filter": false, "flags": [], "cb_kwargs": 
{}}, "num_items": 0, "num_requests": 1}, "2": {"request": {...}}}
```

--- 
## Command line interface

- [`testmaster parse`](#testmaster-parse): makes a number of command-line specified requests and automatically generates testcases (if conditions meet) 
- [`testmaster establish`](#testmaster-establish): generates a directory with a `config.py` file for every callback specified
- [`testmaster update`](#testmaster-update): updates fixtures to test code changes or with a view to guarding against website changes
- [`testmaster inspect`](#testmaster-inspect): inspects fixtures returning a JSON object
- [`testmaster clear`](#testmaster-clear): clears the specified fixtures and re-arranges the rest to restore linearity


#### N.B.
`testmaster parse`, `testmaster establish` and `scrapy crawl my_spider`, when called with the middlewares enabled,  automatically generate the basic testmaster project skeleton if it doesn't exist already (i.e. *testmaster/tests*). The former two do not overwrite anything, but `scrapy crawl` will. (Unlike in Scrapy Autounit, `scrapy crawl` doesn't nuke the entire test directory for the spider in question but instead just immediately overwrites existing fixtures. And like `parse` and `update`, it will pay attention to your rules and settings in any existing `config.py` files)   


### `testmaster parse`
This is just like `scrapy parse` (https://docs.scrapy.org/en/latest/topics/commands.html#std-command-parse) but with greater powers: a greater diversity of requests can be specified and multiple urls can be inputted. Furthermore, if you enable `TestMasterMiddleware`, then the requests triggered by this command will be used to create new testcases, assuming the results pass any custom rules you set down and you haven't reached the max fixtures limit. 

`testmaster parse` takes exactly the same arguments/options as `scrapy parse`, plus three additional options: headers, cookies, and `--homepage` (to visit the website homepage to pick up one or more session token/s before the primary requests are kicked off). The url argument remains the same except that many urls can be inserted at once, separated by `|`, i.e. `"https://www.exampledomain.com/page1|https://www.exampledomain.com/page2|https://exampledomain.com/page2"`. (This used to be comma-separation, and was changed as of version 1.0.) The depth argument is (of course) re-calibrated for the input plurality. 

Like `scrapy crawl`, this command will not write any tests automatically unless `TestMasterMiddleware` is enabled. Unlike `scrapy crawl`, this command will never generate tests/fixtures that overwrite existing ones; it is additive only (though also beholden to ***TESTMASTER_MAX_FIXTURES_PER_CALLBACK**).

One miscellaneous thing to note is that if you have a set value for **TESTMASTER_EXTRA_PATH** in your settings, this command will observe this value, i.e. it will create/update the directory 'testmaster/tests/[extra_path]/spider_name/callback_name'.

Example:
```
$ testmaster parse "url1,url2,url3" --spider=my_spider -c my_callback --meta='{"x":"y"}' --homepage -d 2...
```
Because of the `homepage` arg, this will first try to grab a homepage value from the `start_urls` field for `my_spider` (it will move on if it fails). It will pick up cookies from the homepage if possible, then use these to make the requests to the specified urls. Because of the `--depth=2` arg, it will make one further request for each of the three requests that lead to another request in `my_callback`. For each of the requests generated, a fixture will be written subject to the usual conditions and/or custom rules, and (as with the Scrapy parse command) the scraped items will be printed to the terminal for perusal.  

#### Why doesn't `scrapy parse` take multiple urls?
I suspect its developers figured that if the requests need to be made in a similar manner across different webpages, those webpages cannot nontrivially differ. But I've found in my own scraping efforts that this is an incorrect assumption in a large number of cases. For example, it is common that one's callback code accounts differently for pages with no data versus non-empty pages, or pages with a data field X differently from pages without, and the requests to these two classes of page can be made in the same way (in the simplest case, with default headers and no cookies). Certainly, there is still an infinity of websites out there where most/all of the pages within the domain can be accessed without page-specific headers or parameters. So it's very useful to have a command which allows you to test several differing cases with one call.  
<br/>
  
### `testmaster establish`
This command is simply for setting up the directory structure for a given spider or for a specific spider + callback without having to make any requests. It is not strictly necessary to use this command because `scrapy crawl` and `testmaster parse` will set up the directory structure on their own when they generate tests. Its raison d'etre is the case where it is desirable to define custom behaviour for debugging (for processing the testcases before they become inscribed fixtures) before making any requests. 
Below is an example of this command and the result.
```
$ testmaster establish my_spider -c my_callback
```
```
├── testmaster
│   ├── __init__.py
│   └── tests
│       ├── __init__.py
│       └── my_spider
│           ├── __init__.py
│           └── my_callback
│               ├── __init__.py
│               ├── config.py
```
Without the callback argument, it creates multiple subdirectories for each callback in the spider (identified using nothing more intelligent than regex, i.e. matches functions with args including "response" keyword). Example:
```
├── testmaster
│   ├── __init__.py
│   └── tests
│       ├── __init__.py
│       └── my_spider
│           ├── __init__.py
│           ├── my_callback
│           │   ├── __init__.py
│           │   └── config.py
│           └── my_callback1
│               ├── __init__.py
│               └── config.py
```
This command will observe the **TESTMASTER_EXTRA_PATH** in your settings.  
<br/>


### `testmaster inspect`

To inspect a fixture's data, you need to pass the spider, callback and fixture name to the command:
```
$ testmaster inspect my_spider my_callback fixture3
```
The fixture can also be passed as a number indicating which fixture number to inspect like this:
```
$ testmaster inspect my_spider my_callback 3
```

#### Extracted Data (unchanged from Scrapy Autounit)
This command returns a JSON object that can be parsed with tools like `jq` to inspect specific blocks of data.  

The top-level keys of the JSON output are:  

***`spider_name`***  
The name of the spider.  

***`request`***  
The original request that triggered the callback.  

***`response`***  
The response obtained from the original request and passed to the callback.  

***`result`***  
The callback's output such as items and requests.  

***`middlewares`***  
The relevant middlewares to replicate when running the tests.  

***`settings`***  
The settings explicitly recorded by the *`TESTMASTER_INCLUDED_SETTINGS`* setting.  

***`spider_args`***  
The arguments passed to the spider in the crawl.  

***`python_version`***  
Indicates if the fixture was recorded in python 2 or 3.  

Then for example, to inspect a fixture's specific request we can do the following:
```
$ testmaster inspect my_spider my_callback 4 | jq '.request'
```
<br/>

### `testmaster update`
You can update your fixtures to match your latest changes in a particular callback to avoid running the whole spider.  

This updates the results for all the fixtures for a specific callback:
```
$ testmaster update my_spider -c my_callback
```

This updates the results for all the fixtures for a spider:
```
$ testmaster update my_spider
```

This completely replaces all the fixtures for a specific callback, by re-downloading the response using the original request. (It also downloads, and potentially creates a fixture out of, any requests specified in the "REQUESTS_TO_ADD" field.)
```
$ testmaster update my_spider -c my_callback --dynamic
```

This completely replaces all the fixtures for a spider:
```
$ testmaster update my_spider --dynamic
```

Conversely, you can specify a particular fixture to update with `-f` or `--fixture`:
```
$ testmaster update my_spider -c my_callback --fixture 4
```
(And of course, this can be paired with `--dynamic` to replace the fixture.)

This updates all the results for all the fixtures for a spider, and downloads the requests in the **REQUESTS_TO_ADD** field in `config.py` for the specified callback.
```
$ testmaster update my_spider -c my_callback --new
```
(As before, this command can be executed for all callbacks, rather than just one, if desired.)

As shown by the above, any call of `testmaster update` with `--dynamic` or `--new` options towards a particular callback will automatically trigger the execution of any requests set down in the REQUESTS_TO_ADD list within the relevant config.py file. If these requests are successful according to your rules, and there is space in the fixtures buffer for that particular callback, these requests will result in corresponding fixtures being added. (This is the only way to trigger the execution of these requests.)

`testmaster update` will refuse to write its updates if the results fail any of your custom rules or configuration options. So you don't have to worry about your fixtures being overwritten with junk. This means you can use this command to check the correctness of changes to your code in a more fine-grained way than the Scrapy Autounit library enables.  

#### Caveats
If you have used the 'extra path' setting to set up two or more classes of test for a single spider (perhaps because that spider has multiple distinct configurations), then `testmaster update` will only update any fixtures that can be found using the value for this `extra path` setting in settings.py at the moment you execute the command. So to update all the fixtures for that spider, across all its configurations, you have to repeatedly edit the extra path value in settings.py and call `testmaster update my_spider` for every distinct configuration/extra path. If this is a common situation for people to find themselves on and they find this inconvenient, let me know and I will add the feature that you can specify an extra path on the command-line.  
<br/>

### `testmaster clear`
This allows you to clear out old fixtures that you no longer need. This may be the case, for example, if the request to which the fixture corresponds no longer works for the website in question (so that there is no hope of fixing it via `testmaster update ... --dynamic`).

All arguments are obligatory. Example usage:
```
$ testmaster clear my_spider my_callback 5,10,11'
```
This will cause fixtures 5, 10, 11 to disappear from the callback specified. Then the others will be renamed, so that fixture 6 becomes fixture 5, 7 becomes 6 and so on. Finally, the `view.json` file is updated to match this re-numbering.

<br/>

---
## What is the Use Case for this Library?
The idea behind this project is to provide a set of robust, effective testing and debugging tools for large Scrapy codebases. Here is how I see this library being used in this high-maintenance/enterprise context:

As the developer is programming the spider, she debugs her code, and refines her selectors, by calling `testmaster parse` on various urls. She thereby automatically generates tests/fixtures for every callback each time these requests lead to results that pass any custom rules she has set down (so the debugging and test-generation process is neatly entwined). She can then supplement these fixtures, if she requires, by further calls of `testmaster parse`. Alternatively, if she is satisfied with her code, she can just run `scrapy crawl` to generate a set of fresh fixtures. With these fixtures in place, she can feel secure with every change she makes to her code by running the appropriate tests using `python -m unittest ...`. Once this initial development phase is all done --- she has a number of solid test-cases in place for each callback, and her spider code is working --- she can now boost the likelihood of continuous, effective deployment of her spider by running `update --dynamic ...` on appropriate callbacks at regular intervals to re-download the relevant test pages. By regularly re-downloading the same requests and testing the output, she will remain alert to any changes to the target website which affect the viability of the code.

Of course, the casual Scrapy user will not be concerned with running regular dynamic test updates, but there is no penalty for using only a subset of the capabilities!  

---
## The Example Project
The example project contains two Scrapy spiders, one called "olympus" which crawls this basic website: http://olympus.realpython.org/profiles, and another called "shopify" which can grab products from the public API endpoint of Shopify websites (and by default gets products from the top 5 Shopify websites according to this website (https://www.shopistores.com/top-500-most-successful-shopify-stores/) as of 8:15 AM UTC, October 13 2020).  
  
The fixtures that exist in this project currently were generated according to the following algorithm:
1. Alter *example/settings.py* as displayed.
2. Create a *generic_rules.py* file at the head of the project with rules as displayed. 
3. Call `testmaster establish olympus` to generate a fixture folder and *config.py* file for each callback.
4. Call `testmaster establish shopify` to do the same for that spider.
5. Alter *testmaster/tests/olympus/parse_login/config.py* as displayed.
6. Call `testmaster update olympus --new` so as to create a fixture for the FormRequest described in REQUESTS_TO_ADD in that config file.
7. Alter *testmaster/tests/olympus/parse_info/config.py* so as to enforce a primary field constraint (as displayed).
8. Run `scrapy crawl olympus` so as to automatically generate fixtures for *parse* and *parse_info*, validated against *generic_rules.py* and (for the items in *parse_info*) validated against the local config file.
9. Alter the *shopify* config file so as to change the SKIPPED_FIELDS and create another custom item rule to validate the prices for the discounted items in the data.
10. Run `scrapy crawl shopify` until 10 fixtures are generated, validated by *generic_rules.py* and the local config file. 

Possible things to play around with yourself:
1. Inspect the results of the fixtures.
2. Change the generic rules, global settings and/or the local configurations, and then run an update for a given spider and/or callbacks to test whether the fixtures are updated or whether an error message is displayed.
3. Run `testmaster update spider_name --dynamic`  in order to re-download the original requests for one of the spiders.
4.  Expand the number of fixtures for the `shopify` spider in the local config file and run `scrapy crawl shopify` so as to generate more fixtures.
5. Delete the fixture and *view.json* file in *olympus/parse_info*, edit the body field in the request described in the REQUESTS_TO_ADD list in the local config file, and then run `testmaster update olympus parse_login --new` so as to see whether the edited request-dict still logs in successfully.

---
## Architecture/Logic
I will use the `parse` command to illustrate how this package does its automatic
validation and unittest generation with the middlewares switched on. The logic
involved in the `parse` command is more complicated than the others, so if you
can understand this, you can understand everything. Hopefully,
this will be useful for anyone who desires to fix any bugs in this library.

1. After the command-line args are parsed, the `parse` command fires up the
   Scrapy engine to run the specified/inferred spider with the one-off requests specified.
2. Via the logic in *parse.py*, a one-off `start_requests` function is kicked
   off which returns the list of requests initially specified in *parse.py*
   (request pre-processing happens via `prepare_request` in *parse.py*, which
   sets a custom callback for each request).
3. The requests may then undergo further processing via any
   active request-processing subroutines in any active *Downloader Middlewares* in your project (just as if you had generated these requests via a standard
   crawl). 
4. A response is downloaded and the response is processed as usual by the
   various *Downloader Middlewares* components which deal with responses (just
   as if you had generated the response via a standard crawl).
5. The response is fed to the `process_spider_input` function in
   `TestMasterMiddleware` (a standard spider middleware). This function prepares some of the data necessary to
   create the testcase file and places it in the response meta object. 
6. The response arrives at the `callback` function embedded in the
   `prepare_request` function in *parse.py*, which is playing the role of the
   spider callback. The response is parsed inside this function by the correct
   callback and the processed results are stored inside the response meta object.
7. The response and result (but in this case only the outputted requests are
   included in the result and not
   the items, because of a quirk with the `parse` logic) arrive at the `process_spider_output` function in
   `TestMasterMiddleware`. The total results, items included, are obtained from the
   response meta object where they were stored as described in (6.). These results are validated by the
   various custom settings and rules you have established, whether at the project-level
   or at the config-specific level, or a combination of both. 
8. [Still within `process_spider_output`] If the results are
   valid, and there is room in the fixtures, the fixture is written and
   *view.json* is updated. If not, an exception is raised and the next request/response
   is dealt with.
9. Within *parse.py*, global variables have been storing the collected results
   as you have processed the 1 or more requests you kicked off initially. When
   there are no more requests to be triggered, these results are printed
   together (regardless of the failure or success of the results according to
   your validation rules).    
