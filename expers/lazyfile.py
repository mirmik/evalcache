#!/usr/bin/python3

import sys

sys.path.insert(0, "..")

import evalcache
import evalcache.lazyfile

# lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"), encache=False, decache=False)
# lazy = evalcache.Memoize()
lazyfile = evalcache.lazyfile.LazyFile(cache=evalcache.DirCache(".evalcache"), diag=True)


@lazyfile(field="path")
def foo(a, path):
    f = open(path, "w")
    f.close()


foo(3, "mirmik0.dat")
foo(3, path="mirmik1.dat")
foo(path="mirmik2.dat", a=5)
