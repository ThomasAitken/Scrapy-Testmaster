# Scrapy Testmaster

[![PyPI Version]

## Overview

Scrapy-Testmaster is an automatic test-generation, test-execution and general debugging tool for Scrapy spiders.

As far as I am aware, Scrapy TestMaster is the most comprehensive tool yet for the automated debugging and testing of Scrapy spiders. It offers a system of crawler-validation that is robust against both changes to your own code and to changes in the targeted webpages. Its capabilities include the following: 
- Testing your Scrapy functions against specific requests on the fly, using an extended version of the Scrapy parse command (https://docs.scrapy.org/en/latest/topics/commands.html#std-command-parse) that can take any number of urls ([*testmaster parse*](#testmaster-parse)).
- Using the above command to automatically generate testcases and unit tests.
- Generating automatic testcases and unit tests as you run your spider via `scrapy crawl` (exactly like Scrapy Autounit (https://github.com/scrapinghub/scrapy-autounit)).
- Merging the debugging and test-generation processes by designing meta rules to determine whether a fixture (testcase) should be written based on the quality of the parsed results.
- Specifying requests in a config file to be downloaded and evaluated upon the next execution (allows FormRequests, requests with cookies, requests using proxies, etc).
- Designing custom testing/validation rules down to a callback-specific level so as to check the correctness of output in a very fine-grained manner.
- Updating and validation of existing tests via a re-parsing of the original HTML source with the current spider code (a la *autounit update*).
- Updating and validation of existing tests via an additional re-downloading of the HTML source using the same request.

Apart from the wider range of capabilities, the key difference between this and other Scrapy testing libraries that I have encountered is that Scrapy TestMaster *synthesises the processes of debugging and testcase-generation*. First you set up the custom logic for validating the output of your spider/s, then you call `scrapy crawl` or `testmaster parse`. If the results are acceptable, testcases are written; otherwise, you get an informative error message. See [*What is the Use Case for this Library*](#What is the Use Case for this Library?) for more.
  
Here is an example of the directory tree of your project once the fixtures are created:  
```
my_project

├── my_project
│   ├── __init__.py
│   ├── items.py
│   ├── middlewares.py
│   ├── pipelines.py
│   ├── settings.py
│   └── spiders
│       ├── __init__.py
│       └── my_spider.py
├── testmaster
│   ├── __init__.py
│   └── tests
│       ├── __init__.py
│       └── my_spider
│           ├── __init__.py
│           └── my_callback
│               ├── __init__.py
│               ├── config.py
│               ├── fixture1.bin
│               ├── fixture2.bin
│               ├── test_fixtures.py
│               ├── view.json 
└── scrapy.cfg
```

## Acknowledgements
It would be remiss of me to not draw attention to the fact that the structure of my project is very influenced by Scrapy Autounit, and some of the functions from this library exist in my library unchanged. (I've decided to not make scrapy-autounit a dependency of this project, however.) The `scrapy parse` command is, of course, another major influence, the code for which bears a very strong resemblance to `testmaster parse`.

## Installation

```
pip install scrapy_testmaster
```

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
1. Just run your spiders as usual, Scrapy Testmaster will generate them for you. 
```
$ scrapy crawl my_spider
```
2. Automatically generate testcases for specified urls against a specified callback using `testmaster parse`, an extended version of the Scrapy `parse` command chiefly distinguished by its permission of multi-url inputs.
```
$ testmaster parse "url1,url2,url3" --spider=my_spider -c my_callback --meta='{"x":"y"}' ...
```
3. Specify requests to be later executed in JSON format within the `config.py` file for the spider and callback in question (e.g. `"url":"", "headers":{..}, "_class":"scrapy.http.request.form.FormRequest"`}). These will get executed whenever you call `testmaster update` with the appropriate spider, callback args and options (see [`testmaster update`](#testmaster-update), and lead to new fixtures being written subject to the usual conditions.
```
$ testmaster update my_spider -c my_callback
```

The first two of these commands will automatically generate a directory `testmaster` in your project root dir if none exists, containing all the generated tests/fixtures for the spider you just ran, plus two more files (`config.py` and `view.json`). (See the directory tree example above.) `config.py` is analogous to `settings.py` at the root of every Scrapy project. This config file is for specifying the custom logic and rules that your test-results need to pass for the given callback directory in which the file resides. It also allows one to write down requests to be tested the next time you execute `testmaster parse`. `view.json` is simply a convenience for representing what's currently in your fixtures: it is an ordered list of the requests that generated the current fixtures for the callback in question, plus some basic summary stats. It is updated if the fixtures are changed.  

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

It's worth stating that all of the commands in this library apart from `establish` and `inspect` have a debugging/testing purpose. These `unittest` commands are just useful to test your code against existing fixtures without changing them in any way.

### Other specific tasks

###### Setting up testing environment for given spider/callback before making any requests
```
$ testmaster establish my_spider -c my_callback[optional]
```
(If no callback is specified, every single callback in the spider will get its own directory with a `config.py` file.)
###### Generating new tests for specific urls on the fly
```
$ testmaster parse "url1,url2,url3,..." --spider=my_spider -c my_callback --meta='{"x":"y"}' ...
```
###### Testing output against custom rules on the fly
First, set up your rules in the appropriate `config.py` file, then run:
```
$ testmaster parse "url1,url2,url3,..." --spider=my_spider -c my_callback --meta='{"x":"y"}' ...
```
If the results generated by such a command are all fine according to your custom rules, the fixtures/tests will be written (assuming you haven't reached the fixtures cap you set). Otherwise, you will get an error message about the failure mode. This is an example of how you can merge the debugging and test-generation processes.
###### Updating the results of tests in response to changes in spider code (i.e. re-parsing the downloaded source within the fixture)
```
$ testmaster update my_spider -c my_callback --fixture n[optional]
```
(If no fixture is specified, every fixture is changed.)
###### Remaking the entire fixture using the original request to check for a website change (i.e. re-downloading the response)
```
$ testmaster update my_spider -c my_callback --dynamic
```
###### Triggering the download of complex requests (e.g. FormRequests) described in a config.py file
Define a request in JSON format within a config.py file for the relevant callback, and then call:
```
testmaster update my_spider -c my_callback --new
```
If the results of the request triggered by this command pass your custom rules, and there is space in the fixtures, a new fixture will be written for this request and response.



### Important Caveats
* As long as **TESTMASTER_ENABLED** is on, each time you run a spider using `scrapy crawl`, existing tests/fixtures will be over-written, if the results of the requests being made pass your custom rules. However, if you run a specific callback using `testmaster parse`, this over-writing will not apply - fixtures will be added (within the limit you have set by **TESTMASTER_MAX_FIXTURES_PER_CALLBACK**).
* There are a few lines of code in this library that rely on the assumption that you haven't named your spider file differently from the name attribute of the spider itself. So keep these names aligned if you want assurance that everything will always work! (If you always use `scrapy genspider` and don't later edit the file name or spider name, there will, of course, be no problem.)
* Just in case this happens to be relevant, using as keys in your request.meta any of the strings '_parse', '_update' or '_fixture' may lead to unexpected behaviour with the middleware enabled.

### What's the deal with the fixtures?
The fixtures are essentially just test cases for your spider. Exactly as in Scrapy Autounit (https://github.com/scrapinghub/scrapy-autounit), the *fixture%d.bin* files store in binary format a big JSON dict containing the spider name that generated the fixture, the full details of the request, the entire downloaded response body, the result (i.e. a list of items and/or requests corresponding to the generator produced by the callback code), details about the middlewares in play, the spider settings, the spider args, and the Python version. This library offers you two ways of using these fixtures to run your tests, once they've been written: 
1. Run a static test which parses the response using your updated code for the same callback (to check that you have not broken anything by comparing against the results in the fixture).
2. Run a dynamic test which first downloads a new response using the request info encoded in the fixture, and then parses the response using your code for the callback (to check that the website has not changed).

### Project/Spider Settings
#### N.B.
You will notice that there is heavy overlap here with the settings in config.py. So you can set custom validation rules at any level, although any settings specified to a contrary, non-default value in a `config.py` file will take precedence for that particular callback.

**TESTMASTER_ENABLED**  
Set this to `True` or `False` to enable or disable unit test generation when calling `scrapy crawl`, `testmaster parse` or to run `testmaster update` with the `--dynamic` or `--new` options. The other commands are completely unaffected.

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
For security reasons, Testmaster already excludes `Authorization` and `Proxy-Authorization` headers by default, if you want to include them in your fixtures see *`TESTMASTER_INCLUDED_AUTH_HEADERS`*.  
`Default: []`  

**TESTMASTER_INCLUDED_AUTH_HEADERS**  
If you want to include `Authorization` or `Proxy-Authorization` headers in your fixtures, add one or both of them to this list.  
`Default: []`

**TESTMASTER_INCLUDED_SETTINGS**  
Sets a list of settings names to be recorded in the generated test case.  
`Default: []`

**TESTMASTER_EXTRA_PATH**  
This is an extra string element to add to the test path and name between the spider name and callback name. You can use this to separate tests from the same spider with different configurations. This is respected by all methods of creating directories for spiders + callbacks, i.e. `testmaster establish`, `testmaster parse` and `scrapy crawl`.   It is also respected by `testmaster update` when it's working out what fixtures you want to update.  
`Default: None`

**TESTMASTER_OBLIGATE_ITEM_FIELDS**  
This is a meta setting, which can be used to determine whether a result should become part of a fixture (i.e. the basis for a test).
Insert here any field names which you intend to exist in every "item" (as opposed to "request") object outputted by the tests within this project. 
If an item outputted by a request executed while running *testmaster parse* or *scrapy crawl* lacks this field name, the fixture will not be written.
You can set this to a non-default value but override for specific spiders + callbacks by tweaking the corresponding field in the relevant local config.py file/s.  
`Default: []`

**TESTMASTER_PRIMARY_ITEM_FIELDS**  
Insert here any field names which you intend to be non-empty in every "item" object outputted by the tests within this project.
If an item outputted by a request executed while running *testmaster parse* or *scrapy crawl* has no value for this field (or name), the fixture will not be written. 
It is not necessary to duplicate a field name across this and the above setting; just put the field in this list.
You can set this to a non-default value but override for specific spiders + callbacks by tweaking the corresponding field in the relevant local config.py file/s.   
`Default: []`

**TESTMASTER_PATH_TO_RULES_FILE**  
Insert here a relative path to a .py file containing two classes: `class RequestRules(object)` and `class ItemRules(object)`. Within these classes, you can devise any number of functions, given whatever names you like, that take one argument each: a "request" in the former case and an "item" in the latter. These functions are intended to contain one or more "assertion" statements. These custom rules can have two levels of utility: meta and non-meta. Non-meta: if any of these raise an AssertionError for an extant test, you know that you have made a bad change to your code. Meta: if these assertion statements are violated while Testmaster is evaluating the results of a request that has not yet become a fixture, the fixture will not be written.
If you create such a file, then before any tests are automatically written by `testmaster parse` or `scrapy crawl`, the output will be checked against these rules. All items will be tested against your item rules, and equivalently for requests.  
`Default: None`

---
**Note**: Remember that you can always apply any of these settings per spider including them in your spider's `custom_settings` class attribute - see https://docs.scrapy.org/en/latest/topics/settings.html#settings-per-spider.

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
This is for storing complex requests in Python dict format that will be executed the next time you run any command of `testmaster update` with args indicating the relevant callback, and using either of the options `--dynamic` or `--new` (`--new` means only these requests are downloaded, rather than re-downloading all the existing testcases). It allows you to use all the standard request args as keys plus the "_class" key for specifying a FormRequest or a SplashRequest. The motivation behind it is the extreme 'fiddliness' involved in trying to do the same thing for complex requests using `testmaster parse` on the command-line.  
Example of request format:
```
    {
        "url": "https://examplewebsite011235811.com/info",  
        "callback":"parse_items",
        "headers": {"referer":"...", "content_type": "..."},
        "cookies": {},
        "method": "POST",
        "data": {"x": "y"}, 
        "_class": "scrapy.http.request.form.FormRequest",
        "meta": {"x": "y"}
    }
```
`Default: []`  
All of these keys except "url". The callback is inferred from the location of the config.py file. 
When this request is triggered, it is treated as if you had run `testmaster parse` with the same info. So its response and results can then become part of a new fixture if all your validation rules are passed and there is space.

Currently, you're going to have to delete these requests manually from the `config.py` file to make sure they're not triggered again next time you execute `testmaster update`.

**Other**  
All config.py files will include by default two classes: `class ItemRules(object)` and `class RequestRules(object)`. You can define any number of methods for these classes that take args {*self*, *item*} and {*self*, *request*} respectively. The logic for such methods was explained previously in the precis for **TESTMASTER_PATH_TO_RULES_FILE**.

###Format of view.json  
```
{"1": {"request": {"url": "...", "callback": "...", "errback": null, "method": "GET", "headers": {...}, "body": "", "cookies": {}, "meta": {...}, "_encoding": "utf-8", "priority": 0, "dont_filter": false, "flags": [], "cb_kwargs": {}}, "num_items": 0, "num_requests": 1}, "2": {"request": {...}}}
```

---
## Command line interface

- [`testmaster parse`](#testmaster-parse): makes a number of command-line specified requests and automatically generates tests (if conditions meet) 
- [`testmaster establish`](#testmaster-establish): generates a directory with a `config.py` file for every callback specified
- [`testmaster update`](#testmaster-update): updates fixtures to test code changes or with a view to guarding against website changes
- [`testmaster inspect`](#testmaster-inspect): inspects fixtures returning a JSON object


#### N.B.
`testmaster parse`, `testmaster establish` and `scrapy crawl my_spider`, when called with the middlewares enabled,  automatically generate the basic testmaster project skeleton if it doesn't exist already (i.e. #testmaster/tests). The former two do not overwrite anything, but `scrapy crawl` will. (Unlike in Scrapy Autounit, `scrapy crawl` doesn't nuke the entire test directory for the spider in question but instead just immediately overwrites existing fixtures. And like `parse` and `update`, it will pay attention to your rules and settings in any existing `config.py` files) 


### `testmaster parse`
This is just like `scrapy parse` (https://docs.scrapy.org/en/latest/topics/commands.html#std-command-parse) but with greater powers --- a greater diversity of requests can be specified and multiple urls can be inputted. Furthermore, if you enable `TestMasterMiddleware`, then the requests triggered by this command will be used to create new testcases, assuming the results pass any custom rules you set down and you haven't reached the max fixtures limit. 

`testmaster parse` takes exactly the same arguments as `scrapy parse`, plus three additional arguments: headers, cookies, and an additional option `--homepage` to visit an (inferred) website homepage to pick up one or more session token/s before the primary requests are kicked off. The url argument remains the same except that many urls can be inserted at once, separated by commas, i.e. "https://www.exampledomain.com/page1,https://www.exampledomain.com/page2,https://exampledomain.com/page2". The depth argument is (of course) re-calibrated for the input plurality. 

Like `scrapy crawl`, this command will not write any tests automatically unless `TestMasterMiddleware` is enabled. Unlike `scrapy crawl`, this command will never generate tests/fixtures that overwrite existing ones; it is additive only (though also beholden to ***TESTMASTER_MAX_FIXTURES_PER_CALLBACK**).

One miscellaneous thing to note is that if you have a set value for **TESTMASTER_EXTRA_PATH** in your settings, this command will observe this value, i.e. it will create/update the directory 'testmaster/tests/[extra_path]/spider_name/callback_name'.

#### Why doesn't `scrapy parse` take multiple urls?
I suspect its developers figured that if the requests need to be made in a similar manner across different webpages, those webpages cannot nontrivially differ. But I've found in my own scraping efforts that this is an incorrect assumption in a large number of cases. For example, it is common that one's callback code accounts differently for pages with no data versus non-empty pages, or pages with a data field X differently from pages without, and the requests to these two classes of page can be made in the same way (in the simplest case, with default headers and no cookies). Certainly, there is still an infinity of websites out there where most/all of the pages within the domain can be accessed without page-specific headers or parameters. So it's very useful to have a command which allows you to test several differing cases with one call.

### `testmaster establish`
This command is simply for setting up the directory structure for a given spider or for a specific spider + callback without having to make any requests. It is not strictly necessary to use this command because `scrapy crawl` and `testmaster parse` will set up the directory structure on their own when they generate tests. Its raison d'etre is the case where it is desirable to define custom behaviour for debugging (for processing the testcases before they become inscribed fixtures) before making any requests. 
Below is an example of this command and the result.
```
$ testmaster establish my_spider -c my_callback
```
```
├── testmaster
│   ├── __init__.py
│   └── tests
│       ├── __init__.py
│       └── my_spider
│           ├── __init__.py
│           └── my_callback
│               ├── __init__.py
│               ├── config.py
```
Without the callback argument, it creates multiple subdirectories for each callback in the spider (identified using nothing more intelligent than regex, i.e. matches functions with args including "response" keyword). Example:
```
├── testmaster
│   ├── __init__.py
│   └── tests
│       ├── __init__.py
│       └── my_spider
│           ├── __init__.py
│           ├── my_callback
│           │   ├── __init__.py
│           │   └── config.py
│           └── my_callback1
│               ├── __init__.py
│               └── config.py
```
This command will observe the **TESTMASTER_EXTRA_PATH** in your settings.


### `testmaster inspect` (unchanged from Scrapy Autounit)

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

### `testmaster update` (extended and altered from Scrapy Autounit)
You can update your fixtures to match your latest changes in a particular callback to avoid running the whole spider.  

In addition to a few extra abilities (see below), there is  major syntactic difference from the `testmaster update` command and the `autounit update` command, viz., that the callback argument is now optional. If not specified, every fixture for a given spider is updated. Another syntactic difference is the addition of two extra options: `--dynamic` and `--new`, explained via the examples below.
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

Another important difference between `testmaster update` and `autounit update` is that the former will refuse to write its updates if the results fail any of your custom rules or configuration options. So you don't have to worry about your fixtures being overwritten with junk. This means you can use this command to check the correctness of changes to your code in a more fine-grained way than the Scrapy Autounit library enables.

#### Caveats
If you have used the 'extra path' setting to set up two or more classes of test for a single spider (perhaps because that spider has multiple distinct configurations), then `testmaster update` will only update any fixtures that can be found using the value for this `extra path` setting in settings.py at the moment you execute the command. So to update all the fixtures for that spider, across all its configurations, you have to repeatedly edit the extra path value in settings.py and call `testmaster update my_spider` for every distinct configuration/extra path. If this is a common situation for people to find themselves on and they find this inconvenient, let me know and I will add the feature that you can specify an extra path on the command-line.

### Brief Note on the Role of `python -m unittest...` Regular Commands
Calling `python -m unittest ...` will not evaluate your test cases against the custom rules you have specified in `settings.py` and/or any relevant `config.py` files. These unittest calls are only for checking that a change to your code hasn't broken anything. Your test cases are meant to be solid examples of desirable output; as previously described, they will only be written if they pass the custom rules you specified when you ran `testmaster parse`, `testmaster update` with `--dynamic` or `--new`, or `scrapy crawl`. If you forgot to specify some custom rules to check your results against before running one of these commands, then update these to the desired values before running `testmaster update` statically to check the responses you already downloaded against your new logic.

## What is the Use Case for this Library?
The idea behind this project is to provide a set of robust, effective testing and debugging tools for large Scrapy codebases. I believe it represents a decent step towards the dream of applying the principle of "continuous integration" to the vagarious art of maintaing lots of webcrawlers. Here is how I see this library being used in this high-maintenance/enterprise context:

As the developer is programming the spider, she debugs her code, and refines her selectors, by calling `testmaster parse` on various urls. She thereby automatically generates tests/fixtures for every callback each time these requests lead to results that pass any custom rules she has set down (so the debugging and test-generation process is neatly entwined). She can then supplement these fixtures, if she requires, by further calls of `testmaster parse`. Alternatively, if she is satisfied with her code, she can just run `scrapy crawl` to generate a set of fresh fixtures. With these fixtures in place, she can feel secure with every change she makes to her code by running the appropriate tests using `python -m unittest ...`. Once this initial development phase is all done --- she has a number of solid test-cases in place for each callback, and her spider code is working --- she can now boost the likelihood of continuous, effective deployment of her spider by running `update --dynamic ...` on appropriate callbacks at regular intervals to re-download the relevant test pages. By regularly re-downloading the same requests and testing the output, she will remain alert to any changes to the target website which affect the viability of the code.

Of course, the casual Scrapy user will not be concerned with running regular dynamic test updates, but there is no penalty for using only a subset of the capabilities!

## Contribution/Issues Policy
Please let me know if you've found an issue or bug with this package, and I'll try to repair it as soon as possible. Feel free to submit a pull request if you know how to fix the problem yourself.
If you have an idea for a feature, I'll be less likely to want to work on it myself unless it's a really good idea. I have other projects to work on. I made sure not to release this until I had implemented every feature I wanted, because I would ideally like to just move on from it.

## On the Tests for this Library
Ironically, this library is somewhat starved of automatic tests at the moment. In terms of the tests that can be found in this project, I adapted the tests that were part of the Scrapy Autounit project and left it at that. This is not to say that it wasn't well-tested; each component was tested as it was completed, but tested via direct execution, with the testcases being projects that belong to a proprietary codebase. It would be very welcome if someone were to write up a stronger automatic test suite. Personally, I'm not going to put any effort into this issue; it is for the world to continue my work on this library, should the world desire.

## Other
My library has fixed an issue with the `update` command that exists in the current version of Scrapy Autounit: https://github.com/scrapinghub/scrapy-autounit/issues/73. Line in cli.py `response = response_cls(request=data['request'], **data['response'])` which should be `response = response_cls(request=request, **data['response'])`.


