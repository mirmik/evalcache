# coding: utf-8

import os
import pickle


class DirCache_v2:
    """Standart dict-like object that store pairs key-value as files
	in target directory.
	Second version store objects with directory prefix like git.

	Arguments:
	----------
	dirpath - target directory path. If it isn't exists, we trying
	to create it.

	Exceptions:
	-----------
	IOException
	"""

    @staticmethod
    def key_prefix(key):
        return key[:2]

    @staticmethod
    def key_to_relpath(key):
        return "{}/{}".format(DirCache_v2.key_prefix(key), key[2:])

    def __init__(self, dirpath):
        self.dirpath = dirpath
        if not os.path.exists(dirpath):
            os.mkdir(dirpath)
            self.prefixes = set()
            self.prefixes_cache = dict()
        else:
            lst = os.listdir(dirpath)
            self.prefixes = set(lst)
            self.prefixes_cache = dict()

    def update_prefix(self, prefix):
        dirpath = os.path.join(self.dirpath, prefix)
        if not os.path.exists(dirpath):
            os.mkdir(dirpath)
            self.prefixes_cache[prefix] = set()
        else:
            lst = [prefix + rkey for rkey in os.listdir(dirpath)]
            self.prefixes_cache[prefix] = set(lst)

    def __contains__(self, key):
        prefix = self.key_prefix(key)
        if prefix not in self.prefixes:
            return False

        if prefix not in self.prefixes_cache:
            self.update_prefix(prefix)

        return key in self.prefixes_cache[prefix]

    def __setitem__(self, key, value):
        prefix = self.key_prefix(key)

        if prefix not in self.prefixes_cache:
            self.update_prefix(prefix)

        with open(os.path.join(self.dirpath, self.key_to_relpath(key)), "wb") as fl:
            pickle.dump(value, fl)
        self.prefixes_cache[prefix].add(key)

    def __getitem__(self, key):
        prefix = self.key_prefix(key)

        if prefix not in self.prefixes_cache:
            raise KeyError

        if key not in self.prefixes_cache[prefix]:
            raise KeyError

        with open(os.path.join(self.dirpath, self.key_to_relpath(key)), "rb") as fl:
            return pickle.load(fl)

    def __delitem__(self, key):
        prefix = self.key_prefix(key)

        if prefix not in self.prefixes_cache:
            raise KeyError

        if key not in self.prefixes_cache[prefix]:
            raise KeyError

        os.remove(os.path.join(self.dirpath, self.key_to_relpath(key)))
        self.prefixes_cache[prefix].remove(key)

    def keys(self):
        ret = set()

        for p in self.prefixes:
            self.update_prefix(p)

        for p in self.prefixes_cache:
            ret = ret.union(self.prefixes_cache[p])

        return list(ret)

    def makePathTo(self, key):
        """Create path to hashable data with key"""
        self.update_prefix(self.key_prefix(key))
        return os.path.join(self.dirpath, self.key_to_relpath(key))
