#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
#lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"), encache=False, decache=False)
lazy = evalcache.Memoize()

@lazy
def foo():
	print("foo")
	return 33

a = foo()
b = foo()

print(a)
print(b)