#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
import math

lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))

@lazy 
def foo():
	return 1

@lazy
def summ(*args):
	return sum(args)

a = lazy(2)
b = foo()

function_result = summ(a,b)
print(function_result.unlazy()) #3

operator_add_result = lazy(1) + lazy(2) + lazy(3)
print(operator_add_result.unlazy()) #6