#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
import shelve
lazy = evalcache.Lazy(cache = shelve.open(".shelve"), diag = True)

@lazy
def foo():
	return 1

a = foo().unlazy()

print(a)