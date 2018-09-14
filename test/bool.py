#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"), diag = True)

a = lazy(0)

print(a)

if bool(a):
	print(True)
else:
	print(False)

print(int(a + 26))