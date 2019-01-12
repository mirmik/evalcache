#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
import math

#lazy = evalcache.Memoize(onplace = False, diag=True, print_invokes=True, print_values=True)
lazy = evalcache.Memoize(onplace = True)

@lazy
def fib(n):
	if n < 2:
		return n
	return fib(n - 1) + fib(n - 2)

#a = fib(10)
#b = fib(8)
#print(fib(20))

for i in range(0,100):
	print(fib(i))