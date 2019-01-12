#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))


def foo():
	lmb_1 = lambda: 1
	lmb_2 = lambda: 2
	
	lazy_1 = lazy(lmb_1, hint="a")()
	lazy_2 = lazy(lmb_2, hint="b")()
	
	lazy1 = lazy(lmb_1)()
	lazy2 = lazy(lmb_2)()
	
	print(lazy_1.unlazy())
	print(lazy_2.unlazy())
	print(lazy1.unlazy())
	print(lazy2.unlazy())

foo()