# EvalCache
Lazy tree evaluation cache library.

## Brief
The library implements a cache of dependent lazy calculations for working with clean, time-consuming computational tasks, such as symbolic transformations, geometric, numerical algorithms.

The task of the library is to save the result of the computation once performed and, if necessary, load it, saving the computing resources. The algorithm for constructing the hashkey of the computed object uses the input data parameterizing this object, which makes it possible to track changes in the arguments of the lazy algorithm and to postpone the necessary calculations if the conditions have changed. If an lazy object is used as an argument or a generating function, its hashkey is used as its hash. This allows you to build a dependent computational tree. If the input data of an object changes, its hashkey and hashkeys of all objects computed on its basis change. And the subtree will be reevaluated.

Since the library saves every computed object in the cache, including intermediate objects, it can pick up changes in the calculation tree from any step. Thus, previously received data, if they can be applied to a new calculation tree, will be used. This allows you to not make heavy preliminary calculations in separate files, and load them transparently, and also compare results with small changes in input parameters without multiple results remaking.

## Install
```sh
python3 -m pip install evalcache
```

## Details
### Base example
```python
import evalcache

lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))

@lazy
def func(a,b,c):
    return do_something(a,b,c)

lazyresult = func(1,2,3)
result = lazyresult.unlazy() #alternative: result = evalcache.unlazy(lazyresult)
```

In that example we can see based classes and objects:
You should instance "evalcache.Lazy" for start work. "Lazy" get "cache" as parametr. Cache is a dict-like object those will store and load our evaluation's results. "Lazy" instance "lazy" can be used as decorator for create "LazyObjects". Decorated object "func" is a LazyObject. "func" can generate another lazyobject, as "lazyresult", for example with callable interface. For get evaluation result we use "unlazy" method.

### Diagnostic  
We can visualize cache operations:
```python
lazy = evalcache.Lazy(cache = cache, diag = True)
```
in this mode, when you use unlazy, you will see console output:  
endp - get endpoint object.  
fget - get variable from local object store.  
load - get early stored value from cache.  
save - evaluation executed and value stored.
eval - evaluated without storing

### Hash algorithm  
You can choose algorithm from hashlib or specify user's hashlib-like algorithm.
```python
lazy = evalcache.Lazy(cache = cache, algo = hashlib.sha512)
```

### DirCache
DirCache is a dict-like object that used pickle to store values in key-named files.
It very simple cache and it can be changed to more progressive option if need. 
```python
lazy = evalcache.Lazy(cache = evalcache.DirCache(".evalcache"))
```  
### Articles
[Дисковое кэширование деревьев ленивых вычислений](https://habr.com/post/422937/)

### Contact
mirmik(mirmikns@yandex.ru)
