#!/usr/bin/python3

import sys

sys.path.insert(0, "..")

import evalcache


def run(cache_dir=".evalcache"):
    """Run implicit example once."""
    lazy = evalcache.Lazy(cache=evalcache.DirCache(cache_dir))

    @lazy
    def foo(a):
        return a * a

    res = foo(3)
    return res.unlazy()


def main():
    print(run())


if __name__ == "__main__":
    main()
