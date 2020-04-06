import os
import pickle

import logger

class FileCache:
    def __init__(self, cache_root="cache", logger=logger.create_logger(__name__)):
        self.cache_root = cache_root
        self.logger = logger

    def __contains__(self, key):
        filename = self.__key_to_path(key)
        return os.path.exists(filename)

    def write(self, key, value):
        filename = self.__key_to_path(key)
        self.logger.debug("Cache write: {}".format(filename))
        cache_file = open(filename, 'wb')
        cache_file.write(pickle.dumps(value))

    def read(self, key):
        filename = self.__key_to_path(key)
        self.logger.debug("Cache read: {}".format(filename))
        cache_file = open(filename, 'rb')
        return pickle.loads(cache_file.read())

    def __key_to_path(self, key):
        return "{}/{}".format(self.cache_root, key)
