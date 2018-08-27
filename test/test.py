#!/usr/bin/python3
#coding: utf-8

import inspect
import sys
sys.path.insert(0, "..")

import evalcache
from evalcache.dirdict import dirdict
import hashlib

lazy = evalcache.Lazy(cache = dirdict(".evalcache"), algo = hashlib.sha256)

class A:
	i=42
	
	def __init__(self, i):
		self.i = i

	def __add__(self, other):
		try:
			return A(self.i + other.i)
		except:
			return A(self.i + other)

	def left(self):
		return A(self.i+1)

	def __str__(self):
		return str("A: {}".format(self.i))

create_A = lazy.ctor(A)

@lazy
def foo(i):
	return 3 + i

print(foo(7).__lazyeval__())
print(foo(7).__lazyeval__())
a= create_A(33)

print(evalcache.unlazy(a))
print(evalcache.unlazy(a.left()))