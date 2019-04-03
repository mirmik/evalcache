#!/usr/bin/python3

import sys

sys.path.insert(0, "..")

import evalcache
import hashlib
import shelve

lazy = evalcache.Lazy(cache=shelve.open(".cache"), algo=hashlib.sha256)


@lazy
def summ(a, b, c):
    return a + b + c


@lazy
def sqr(a):
    return a * a


a = 1
b = sqr(2)
c = lazy(3)

lazyresult = summ(a, b, c)
result = lazyresult.unlazy()

print(lazyresult)  # f8a871cd8c85850f6bf2ec96b223de2d302dd7f38c749867c2851deb0b24315c
print(result)  # 8

evalcache.print_tree(lazyresult)
