'''All of the below settings apply only within the level that this config file 
is situated. However, some of these options can also be applied at a
project-level within settings.py (see the docs for info on which options
transfer). Note that any inconsistencies are resolved in favour of the more
'local' settings, unless the local settings are the default whereas the global
is non-default. 

Example: If TESTMASTER_OBLIGATE_ITEM_FIELDS in settings.py is unchanged but you
have edited OBLIGATE_ITEM_FIELDS in this config.py file, those local changes
will be applied to the tests for the callback. On the other hand, if you have
tweaked a global setting in settings.py, that setting will apply to every single
test in the project for which the relevant config.py file displays the default
option.

As for any custom rules you define under ItemRules or RequestRules, these will
be executed before any global custom rules, but they do not replace them.'''

#Equivalent to TESTMASTER_MAX_FIXTURES_PER_CALLBACK in settings.py
MAX_FIXTURES = 10

#Equivalent to TESTMASTER_SKIPPED_FIELDS
SKIPPED_FIELDS = []

#Equivalent to TESTMASTER_REQUEST_SKIPPED_FIELDS
REQUEST_SKIPPED_FIELDS = []

#Equivalent to TESTMASTER_EXCLUDED_HEADERS
EXCLUDED_HEADERS = []

#Equivalent to TESTMASTER_INCLUDED_AUTH_HEADERS
INCLUDED_AUTH_HEADERS = []

#Equivalent to TESTMASTER_INCLUDED_SETTINGS
INCLUDED_SETTINGS = []


# Insert here any field names which you intend to exist in every dictionary
# object outputted for all callback/s applicable at the given level of this file
# (does not affect callbacks which output requests). 

#Equivalent to TESTMASTER_OBLIGATE_ITEM_FIELDS
OBLIGATE_ITEM_FIELDS = []

# Insert here any field names which you intend to exist and be non-empty in
# every dictionary object outputted for all callback/s applicable at the given
# level of this file (does not affect callbacks which output requests)

#Equivalent to TESTMASTER_PRIMARY_ITEM_FIELDS
PRIMARY_ITEM_FIELDS = []

'''If a field appears in PRIMARY_ITEM_FIELDS and OBLIGATE_ITEM_FIELDS, the former
takes precedence.'''


# Now you can specify any additional requests involving a dynamic download, similar
# to the "scrapy parse" command, but with extra options! These requests will be
# triggered (with their data potentially becoming new fixtures) the next time
# you call "testmaster update" specifying this callback. 

# Format = Python dicts, not JSON (i.e. use None & True not null and true); 
# field "_class" can be omitted for standard requests
REQUESTS_TO_ADD = [
    #{
        # "url": "https://examplewebsite011235811.com",  
        # "headers": {"referer":"...", "content_type": "..."},
        # "cookies": {},
        # "method": "POST",
        # "data": {"x": "y"}, 
        # "_class": "scrapy.http.request.form.FormRequest",
        # "meta": {"x": "y"},
    # },
    # {
        # ...
    # }
]


# Add your own rules to test for properties of your output! These will be added to 
# the default rules which just check for differences against the results of the 
# original test.

class ItemRules(object):
#   def example_rule(self, item):
#       assert(float(item["now_price"].strip('$').replace(',', '')) <=
#       float(item["was_price"].strip('$').replace(',', '')))
    pass
    
class RequestRules(object):
#   def example_rule(self, request):
#       if request["meta"].get("categories", []):
#           assert(len(request["meta"]["categories"]) >= 2)
    pass
