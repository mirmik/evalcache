#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import sympy
import evalcache

lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"), diag = True)

x, y = sympy.symbols("x y")

x = lazy(x)

print(x + y)
print(y + x)