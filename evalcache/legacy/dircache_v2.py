# coding: utf-8
"""Original two-level dict-like directory cache used by Lazy."""

import os
import pickle
import tempfile


class DirCache_v2:
    """Standart dict-like object that store pairs key-value as files
	in target directory.
	Second version store objects with directory prefix like git.

    TODO: Оптимизировать множественные загрузки с помощью локального
    хранилища загруженных объектов.

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
        return os.path.join(DirCache_v2.key_prefix(key), key[2:])

    def __init__(self, dirpath):
        self.dirpath = dirpath
        os.makedirs(dirpath, exist_ok=True)
        self.prefixes = set()
        self.prefixes_cache = dict()

        self._tmpdir = os.path.join(self.dirpath, "tmp")
        os.makedirs(self._tmpdir, exist_ok=True)
        self._update_prefixes()

    def _update_prefixes(self):
        self.prefixes = {
            name for name in os.listdir(self.dirpath)
            if name != "tmp" and os.path.isdir(os.path.join(self.dirpath, name))
        }

    def update_prefix(self, prefix):
        dirpath = os.path.join(self.dirpath, prefix)
        os.makedirs(dirpath, exist_ok=True)
        self.prefixes.add(prefix)
        lst = [prefix + rkey for rkey in os.listdir(dirpath)]
        self.prefixes_cache[prefix] = set(lst)

    def __contains__(self, key):
        prefix = self.key_prefix(key)
        path = os.path.join(self.dirpath, self.key_to_relpath(key))
        exists = os.path.isfile(path)
        if exists:
            self.prefixes.add(prefix)
            self.prefixes_cache.setdefault(prefix, set()).add(key)
        elif prefix in self.prefixes_cache:
            self.prefixes_cache[prefix].discard(key)
        return exists

    def __setitem__(self, key, value):
        prefix = self.key_prefix(key)

        if prefix not in self.prefixes_cache:
            self.update_prefix(prefix)

        path = os.path.join(self.dirpath, self.key_to_relpath(key))
        fd, tmppath = tempfile.mkstemp(dir=self._tmpdir)
        try:
            with os.fdopen(fd, "wb") as fl:
                pickle.dump(value, fl)
            os.replace(tmppath, path)
        finally:
            try:
                os.remove(tmppath)
            except FileNotFoundError:
                pass
        self.prefixes_cache[prefix].add(key)

    def __getitem__(self, key):
        path = os.path.join(self.dirpath, self.key_to_relpath(key))
        try:
            with open(path, "rb") as fl:
                return pickle.load(fl)
        except FileNotFoundError:
            raise KeyError(key)

    def __delitem__(self, key):
        prefix = self.key_prefix(key)
        try:
            os.remove(os.path.join(self.dirpath, self.key_to_relpath(key)))
        except FileNotFoundError:
            raise KeyError(key)
        if prefix in self.prefixes_cache:
            self.prefixes_cache[prefix].discard(key)

    def keys(self):
        ret = set()

        self._update_prefixes()
        for p in self.prefixes:
            self.update_prefix(p)

        for p in self.prefixes_cache:
            ret = ret.union(self.prefixes_cache[p])

        return list(ret)

    def makePathTo(self, key):
        """Create path to hashable data with key"""
        self.update_prefix(self.key_prefix(key))
        return os.path.join(self.dirpath, self.key_to_relpath(key))

    def tmpdir(self):
        return self._tmpdir

    def clean_tmp(self):
        for l in os.listdir(self._tmpdir):
            os.remove(os.path.join(self._tmpdir, l))
