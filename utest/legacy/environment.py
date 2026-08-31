#!/usr/bin/python3
# coding:utf-8

import evalcache
import evalcache.dircache
import shutil

import os

dircache_path = ".evalcache"
dircache_path2 = ".evalcache2"

lazy = evalcache.Lazy(cache=evalcache.dircache.DirCache(dircache_path))
memoize = evalcache.Memoize(onplace=False)
onplace_memoize = evalcache.Memoize(onplace=True)


def clean():
    for path in os.listdir(dircache_path):
        os.remove("{}/{}".format(dircache_path, path))
    lazy.cache.files = set()

def full_clean():
	#shutil.rmtree(dircache_path, ignore_errors=False, onerror=None)
	shutil.rmtree(dircache_path2, ignore_errors=False, onerror=None)

def clean_memoize():
    memoize.cache = {}


def clean_onplace_memoize():
    onplace_memoize.cache = {}


def count_cached_objects():
    return len(os.listdir(dircache_path))
