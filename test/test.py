#!/usr/bin/python3
#coding: utf-8

import inspect
import sys
sys.path.insert(0, "..")

import evalcache
import hashlib

evalcache.enable_diagnostic()

lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"), algo = hashlib.sha256)

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

	def dict_argument_test(self, dct):
		return {"a":dct["a"]+1, "b":dct["b"]+1}

	@lazy
	def method(self, i):
		print("helloWorld", i, self.i)
		return i+1

	def __repr__(self):
		return str("A: {}".format(self.i))

create_A = lazy.ctor(A)

@lazy
def foo(i):
	return 3 + i

print(foo(7).__lazyeval__())
print(foo(7).__lazyeval__())
print((foo(7) + foo(33)).unlazy())
a = create_A(33)

print(evalcache.unlazy(a))
print(evalcache.unlazy(a.left()))

dct_result = a.dict_argument_test({"a":42, "b":24})
print(dct_result.unlazy())

evalcache.print_tree(dct_result)

b = A(77)
method_invoke_result = b.method(66)
print("method_invoke_result", method_invoke_result.unlazy())