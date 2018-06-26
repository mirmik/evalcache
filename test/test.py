#!/usr/bin/python3
#coding: utf-8

import inspect
import sys
sys.path.insert(0, "..")

import evalcache
evalcache.enable()

class A:
	i=42
	
	def __init__(self, i):
		self.i = i

	def __add__(self, other):
		try:
			return A(self.i + other.i)
		except:
			return A(self.i + other)

	def left():
		pass

ABind = evalcache.create_class_wrap("ABind", A)
#BBind = evalcache.create_class_wrap("BBind")

#ABind.__wrapmethods__({
#	("left", ABind),
#})

a = ABind()
print(a)

#A = ABind
#A(3)

#@evalcache.lazy(ABind)
#def add(a, b):
#	return a + b


#a = A(1)
#b = A(2)

#add(a, b).left()