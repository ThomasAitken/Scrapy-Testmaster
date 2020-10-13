class ItemRules(object):
    def numeric_id(self, item):
        assert(int(item["id"])),"\"numeric_id\" test failed!"

class RequestRules(object):
    def categories_exist(self, request):
        assert(len(request["meta"]["categories"]) >= 2),"Categories test failed!"    