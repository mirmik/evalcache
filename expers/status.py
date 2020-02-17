#!/usr/bin/python3

import sys

sys.path.insert(0, "..")

import evalcache
import math

cache = evalcache.DirCache(".evalcache")
#cache.clean()

lazy = evalcache.Lazy(
    cache=cache, status_notify=True, diag=True
)

def stcb(obj):
	print("stcb")

	print(evalcache.lazy.collect_tree_information(obj))

def sncb(obj):
	print("sncb")

def ftcb(obj):
	print("ftcb")

def fncb(obj):
	print("fncb")

lazy.set_start_tree_evaluation_callback(stcb)
lazy.set_start_node_evaluation_callback(sncb)
lazy.set_fini_tree_evaluation_callback(ftcb)
lazy.set_fini_node_evaluation_callback(fncb)

a = lazy(1)
b = lazy(2)
c = lazy(3)

d = a + b + c

evalcache.unlazy(d)