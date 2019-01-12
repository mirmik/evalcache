#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))

@lazy
def lazy_print(*args, **kwargs):
	print(*args, **kwargs)

lazy_a = lazy("Hello")
lazy_b = lazy("Foo")
lazy_c = lazy("Hello")
lazy_d = lazy("Bar")

print("a:", lazy_a.unlazy())
print("b:", lazy_b.unlazy())

lazydict_0 = { lazy_a : lazy_b }
lazydict_1 = { lazy_c : lazy_d }
lazydict_2 = { lazy_a : lazy_b, lazy_c : lazy_d } # hash collision, becouse lazy_a and lazy_b have eq hashes.

lazy.decache = False # decache prevented to force lazy_print operation

print("lazydict_2", lazydict_2)
lazy_print("dict_0", lazydict_0).unlazy()
lazy_print("dict_1", lazydict_1).unlazy()
lazy_print("dict_2", lazydict_2).unlazy()