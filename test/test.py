#!/usr/bin/python3
#coding: utf-8

import inspect
import sys
sys.path.insert(0, "..")

import evalcache
#evalcache.enable()

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

ABind = evalcache.create_class_wrap("ABind", A)

ABind.__wrapmethod__(ABind, "left", ABind)

#BBind = evalcache.create_class_wrap("BBind")

#ABind.__wrapmethods__({
#	("left", ABind),
#})

a = ABind(1)

a = a.left()
a = a.left()

print(a.eval())


#.left().eval()
#a = ABind(1) + ABind(2)
#print(a)

#A = ABind
#A(3)

#@evalcache.lazy(ABind)
#def add(a, b):
#	return a + b


#a = A(1)
#b = A(2)

#add(a, b).left()