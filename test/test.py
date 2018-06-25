#!/usr/bin/python3
#coding: utf-8

import sys
sys.path.insert(0, "..")

import evalcache

@evalcache.lazy
def a():
	print ("a")