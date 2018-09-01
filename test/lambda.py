#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))

lmb_1 = lambda: 1
lmb_2 = lambda: 2

lazy_1 = lazy(lmb_1)()
lazy_2 = lazy(lmb_2)()

print(lazy_1.unlazy())
print(lazy_2.unlazy())

lazy_1.unlazy()
lazy_1.unlazy()
lazy_1.unlazy()
lazy_1.unlazy()

class A():
	def foo(self):
		return lazy(lambda: 4)

A().foo()().unlazy()

assert lazy_1.unlazy() != lazy_2.unlazy()