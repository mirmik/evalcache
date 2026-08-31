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

## Decorated computations and typed expressions (v2)

V2 supports the original decorator-first workflow while using typed expression
nodes internally. A decorated call always returns `Deferred[T]`; immediate
mode evaluates it eagerly but retains the same public wrapper type:

```python
import evalcache

evaluator = evalcache.Evaluator(
    cache_policy=evalcache.CachePolicy.disabled(),
)

@evaluator
def add(left: int, right: int) -> int:
    return left + right

result = add(20, 22)
assert isinstance(result, evalcache.Deferred)
assert result.compute() == 42
assert result.unlazy() == 42
```

The return annotation supplies the default result contract. An unannotated
operation accepts a dynamic result, while `@evaluator.operation(result=...)`
can provide an explicit runtime type or `ResultSpec`.

The extended decorator form keeps cache identity and result guarantees close
to the operation definition:

```python
@evaluator.operation(
    operation_id="my-project.build-mesh",
    operation_version="3",
    result=Mesh,
)
def build_mesh(source: Source) -> Mesh:
    ...
```

Keep `operation_id` stable while the meaning of an operation remains stable,
and increment `operation_version` when old cached results must no longer be
reused. Other useful options are an explicit `ResultSpec` with a validator or
custom serializer, `hash_registry` for domain arguments, and
`cacheable=False` for operations that must not use persistent cache. See
`expers/v2_advanced_decorators.py` for an executable example combining these
options.

Module-level `@evalcache.operation` looks up the default evaluator when the
decorated function is called. Policies can therefore be configured once for
small scripts and experiments:

```python
store = evalcache.MemoryCacheStore()
evalcache.configure(cache_store=store)

@evalcache.operation
def square(value: int) -> int:
    return value * value

assert square(12).compute() == 144
```

Use `@evaluator` for explicit policy ownership, `evalcache.configure(...)` for
process-wide defaults, or `evalcache.using_evaluator(...)` for a temporary
default. Deferred values from different evaluators cannot be mixed in one
graph.

`Deferred` supports operations whose lazy meaning is unambiguous. They create
new expression nodes and do not materialize their operands:

```python
@evaluator
def load_values() -> tuple[int, ...]:
    return (6, -4, 3)

values = load_values()
result = 10 + values[0] * 2 - abs(values[1])
assert result.compute() == 18
```

Supported operations are unary `+`, `-`, `abs`, and `~`; arithmetic `+`, `-`,
`*`, `/`, `//`, `%`, and `**`; matrix multiplication `@`; bitwise `&`, `|`,
`^`, `<<`, and `>>`; and indexing with `[]`. Reflected forms such as
`10 - deferred` are supported as well. Comparisons and Python control-flow
boundaries are deliberately separate: comparisons, truth testing, and implicit
iteration raise `TypeError`, so call `compute()` explicitly when a concrete
value is required.

### File artifacts

A file-producing computation can return immutable contents without making its
destination path part of the expression identity:

```python
@evaluator.operation(
    operation_id="my-project.render-report",
    operation_version="1",
    result=evalcache.file_artifact_result(
        type_id="my-project.text-report.v1",
    ),
)
def render_report(value: int) -> evalcache.FileArtifact:
    return evalcache.FileArtifact(
        name="report.txt",
        data="result={}\n".format(value).encode("utf-8"),
        media_type="text/plain",
    )

report = render_report(42)
report.materialize("first.txt")
report.materialize("second.txt")  # the same cached computation
```

`materialize()` writes through a temporary file and atomically replaces the
destination. `FileArtifact.from_path()` snapshots a backend that can only
produce a file. This first implementation carries artifact bytes inside the
cache record; a blob-aware store can later optimize large artifacts without
changing the operation or decorator API. See `expers/v2_file_artifact.py` for
an executable cache-hit example.

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

Domain libraries may use `Expression[T]` and `Evaluator` directly and keep the
expression inside stable public value types. `legacy_expression` can also
treat a v1 `LazyObject` graph as one opaque leaf during migration.

### License

Evalcache is distributed under the [MIT License](LICENSE).

### Contact
mirmik(mirmikns@yandex.ru)
