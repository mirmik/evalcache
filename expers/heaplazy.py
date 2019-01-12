#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.LazyHash(diag = True)

a = lazy(57)
b = lazy(89)
c = lazy(a+b)
d = a+b+c

print(a.unlazy())
print(b.unlazy())
print(c.unlazy())
print(d.unlazy())