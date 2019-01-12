#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))

class A:
	def __repr__(self):
		return "A"

class B:
	pass

lazy(A())
lazy(B())