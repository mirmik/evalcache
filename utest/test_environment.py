#!/usr/bin/python3
# coding:utf-8

import evalcache
import evalcache.dircache

import os

dircache_path = ".evalcache"

lazy = evalcache.Lazy(cache=evalcache.dircache.DirCache(dircache_path))
memoize = evalcache.Memoize(onplace=False)
onplace_memoize = evalcache.Memoize(onplace=True)


def clean():
    for path in os.listdir(dircache_path):
        os.remove("{}/{}".format(dircache_path, path))
    lazy.cache.files = set()


def clean_memoize():
    memoize.cache = {}


def clean_onplace_memoize():
    onplace_memoize.cache = {}


def count_cached_objects():
    return len(os.listdir(dircache_path))
