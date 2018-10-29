# coding: utf-8

import os
import pickle


class DirCache:
    """Standart dict-like object that store pairs key-value as files
    in target directory.

    Arguments:
    ----------
    dirpath - target directory path. If it isn't exists, we trying
    to create it.

    Exceptions:
    -----------
    IOException
    """

    def __init__(self, dirpath):
        self.dirpath = dirpath

        if not os.path.exists(dirpath):
            os.mkdir(dirpath)
            self.files = set()
        else:
            lst = os.listdir(dirpath)
            self.files = set(lst)

    def __contains__(self, key):
        return key in self.files

    def __setitem__(self, key, value):
        with open(os.path.join(self.dirpath, key), "wb") as fl:
            pickle.dump(value, fl)
        self.files.add(key)

    def __getitem__(self, key):
        with open(os.path.join(self.dirpath, key), "rb") as fl:
            return pickle.load(fl)

    def makePathTo(self, key):
        """Create path to hashable data with key"""
        return os.path.join(self.dirpath, key)