# EvalCache
Lazy tree evaluation cache library.

## Brief
The library implements a cache of dependent lazy calculations for working with clean, time-consuming computational tasks, such as symbolic transformations, geometric, numerical algorithms.

The task of the library is to save the result of the computation once performed and, if necessary, load it, saving the computing resources. The algorithm for constructing the hashkey of the computed object uses the input data parameterizing this object, which makes it possible to track changes in the arguments of the lazy algorithm and to postpone the necessary calculations if the conditions have changed. If an lazy object is used as an argument or a generating function, its hashkey is used as its hash. This allows you to build a dependent computational tree. If the input data of an object changes, its hashkey and hashkeys of all objects computed on its basis change. And the subtree will be reevaluated.

Since the library saves every computed object in the cache, including intermediate objects, it can pick up changes in the calculation tree from any step. Thus, previously received data, if they can be applied to a new calculation tree, will be used. This allows you to not make heavy preliminary calculations in separate files, and load them transparently, and also compare results with small changes in input parameters without multiple results remaking.

## Detail

## Install
```sh
pip3 install evalcache
```

## Base syntax example
```python
import evalcache

lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))

@lazy
def func(a,b,c):
    return do_something(a,b,c)

lazyresult = func(1,2,3)
result = lazyresult.unlazy()
```

## Contact
mirmik(mirmikns@yandex.ru)
