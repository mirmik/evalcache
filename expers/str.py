#!/usr/bin/env python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"), diag = True)

a = lazy(42)

print(a)
lazy.onstr=True
print(a)

print(repr(a))
lazy.onrepr=True
print(repr(a))