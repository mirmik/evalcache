#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
lazy = evalcache.Lazy(".evalcache")

@lazy
def gen():
	return [1,2,3]

arr = gen()

print (arr)

print(len(arr))
iter(arr)

for a in arr:
	print(a.unlazy())