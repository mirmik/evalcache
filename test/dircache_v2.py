#!/usr/bin/python3

import sys
sys.path.insert(0, "..")

import evalcache
import evalcache.dircache_v2

dc = evalcache.dircache_v2.DirCache_v2(".dircache")

dc ["mmmfsadfa"] = 33
print(dc["mmmfsadfa"])