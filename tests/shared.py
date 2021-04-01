import os


class Settings(object):
    def getlist(self, attr_name, default=[]):
        try:
            return getattr(self, attr_name)
        except AttributeError:
            return default

    def get(self, attr_name, default=None):
        try:
            return getattr(self, attr_name)
        except AttributeError:
            return default


def write_config(file_string):
    with open('config.py', 'w') as f:
        f.write(file_string)


def del_config():
    os.remove('config.py')
