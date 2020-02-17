#!/usr/bin/python3

import sys

sys.path.insert(0, "..")

import evalcache
import math

cache = evalcache.DirCache(".evalcache")
cache.clean()

lazy = evalcache.Lazy(
    cache=cache, status_notify=True
)

def stcb(root):
	arr = evalcache.lazy.tree_objects(root)
	print("total:{}".format(len(arr)))

def sncb(root, obj):
	arrs = evalcache.lazy.tree_needeval(root)
	print("toload:{} toeval:{}".format(len(arrs.toload), len(arrs.toeval)))

def ftcb(root):
	pass
	#print("ftcb")

def fncb(root, obj):
	arrs = evalcache.lazy.tree_needeval(root)
	print("toload:{} toeval:{}".format(len(arrs.toload), len(arrs.toeval)))
	#print("fncb")

lazy.set_start_tree_evaluation_callback(stcb)
lazy.set_start_node_evaluation_callback(sncb)
lazy.set_fini_tree_evaluation_callback(ftcb)
lazy.set_fini_node_evaluation_callback(fncb)

a = lazy(1)
b = lazy(2)
c = lazy(3)

d = a + b + c

evalcache.unlazy(d)