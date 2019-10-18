#!/usr/bin/env python3

import evalcache
import hashlib

lazy = evalcache.Memoize(algo = hashlib.sha512)

print(lazy((11,0)).__lazyhash__)
print(lazy((1,10)).__lazyhash__)
print(lazy([11,0]).__lazyhash__)
print(lazy([1,10]).__lazyhash__)
print()