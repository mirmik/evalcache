#!/usr/bin/python3

import sys

sys.path.insert(0, "../..")

import evalcache

lazy = evalcache.Lazy(cache=evalcache.DirCache(".evalcache"))


@lazy
def foo():
    return 2


print(foo().unlazy())
