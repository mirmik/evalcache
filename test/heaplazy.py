#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.HeapLazy(diag = True)

a = lazy(57)
b = lazy(89)
c = lazy(a+b)
d = a+b+c

print(a)
print(b)
print(c)
print(d)