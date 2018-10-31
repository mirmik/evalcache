#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
import math

#lazy = evalcache.Memoize(strategy="onuse", diag=True, print_invokes=True)
lazy = evalcache.Memoize(onplace=False, diag=True)

@lazy 
def foo():
	return 1

@lazy 
def bar():
	return 2

@lazy 
def gen(a):
	return 3 + a

#a = lazy(2)

print(bar)


a = foo()
b = bar()

print(a + b)
print(a - b)
print(a * b)
print(a / b)
print(a % b)


print(a + b)
print(a + b)
print(a + b)
print(a + b)
print(a + b)
print(a + b)

print(a + b - gen(1))
print(a - gen(1))
print(a + gen(2))