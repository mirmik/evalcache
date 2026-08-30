# EvalCache
Lazy tree evaluation cache library.

![](https://travis-ci.com/mirmik/evalcache.svg?branch=master)

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

## Typed expression kernel (v2)

The legacy `LazyObject` API remains available for existing applications. New
domain libraries can instead keep a typed `Expression[T]` inside their own
public value objects and resolve it through an `Evaluator`:

```python
import evalcache

integer = evalcache.ResultSpec.for_type(int)
evaluator = evalcache.Evaluator(
    mode=evalcache.EvaluationMode.DEFERRED,
    cache_policy=evalcache.CachePolicy.disabled(),
)
expression = evaluator.expression(
    lambda left, right: left + right,
    result=integer,
    args=(20, 22),
    operation_id="example.add",
    operation_version="1",
)
assert evaluator.evaluate(expression) == 42
```

`Expression.create` snapshots the computation structure and calculates a
deterministic digest. Arguments must be immutable and deterministically
hashable; application types register an encoder with `HashRegistry` or expose
`__evalcache_key__() -> bytes`. Lists, tuples, sets, frozensets, and mappings
retain their container type during resolution.

Persistent caching is split into three explicit contracts:

- `CachePolicy` controls reads, writes, namespace, and corrupt-record recovery;
- `CacheStore` stores versioned records (`MemoryCacheStore` and
  `MappingCacheStore` are supplied);
- each `ResultSpec[T]` owns a `Serializer[T]`, which may emit named binary
  `Artifact` values alongside its payload.

The default `PickleSerializer` is only suitable for cache directories trusted
by the current user. Use a non-executable serializer whenever cache data can
cross a trust boundary.

`legacy_expression` is a temporary migration bridge. It treats a v1
`LazyObject` graph as one opaque leaf and validates the resolved result; it is
not the extension API for new code.

### Contact
mirmik(mirmikns@yandex.ru)
