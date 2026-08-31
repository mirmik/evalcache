#!/usr/bin/python3

import sys

sys.path.insert(0, "..")

import evalcache

lazy = evalcache.Lazy(cache=evalcache.DirCache(".evalcache"), diag=True)


@lazy
def foo():
    return 42


@lazy
def bar():
    return foo()


print(bar().unlazy())
