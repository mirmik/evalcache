#!/usr/bin/python3
#coding: utf-8

import sys
sys.path.insert(0, "..")

import evalcache

@evalcache.lazy
def add(a, b):
	return a + b

evalcache.enable()

class A:
	def __init__(self, i):
		self.i = i

	def __add__(self, other):
		try:
			return A(self.i + other.i)
		except:
			return A(self.i + other)

	def __str__(self):
		return str(self.i)

a = A(1)
b = A(2)

print( add(add(a, b), 33).eval() )