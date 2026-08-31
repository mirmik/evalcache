"""Original Lazy API retained for existing programs."""

from evalcache.legacy.dircache import DirCache
from evalcache.legacy.dircache_v2 import DirCache_v2
from evalcache.legacy.lazy import (
    Lazy,
    LazyHash,
    LazyObject,
    Memoize,
    decache,
    encache,
    nocache,
    print_tree,
    unlazy,
    unlazy_if_need,
)
from evalcache.legacy.lazyfile import LazyFile
from evalcache.legacy.util import filter, map, reduce, select


__all__ = [
    "DirCache",
    "DirCache_v2",
    "Lazy",
    "LazyFile",
    "LazyHash",
    "LazyObject",
    "Memoize",
    "decache",
    "encache",
    "filter",
    "map",
    "nocache",
    "print_tree",
    "reduce",
    "select",
    "unlazy",
    "unlazy_if_need",
]
