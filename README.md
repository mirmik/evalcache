# EvalCache

Decorator-first caching for graphs of expensive Python computations.

[![CI](https://github.com/mirmik/evalcache/actions/workflows/ci.yml/badge.svg)](https://github.com/mirmik/evalcache/actions/workflows/ci.yml)

EvalCache turns calls to pure functions into deferred expression nodes. The
result of every node can be reused from memory or a persistent cache, including
intermediate nodes shared by several computations.

## Install

```sh
python -m pip install evalcache
```

## Basic use

```python
import evalcache

evalcache.configure(
    cache_store=evalcache.DirectoryCacheStore(".evalcache"),
)

@evalcache.operation
def preprocess(source: str) -> list[int]:
    print("preprocessing", source)
    return [1, 2, 3]

@evalcache.operation
def total(values: list[int]) -> int:
    return sum(values)

result = total(preprocess("model.step"))

# Decorated calls build a graph and return Deferred values.
assert isinstance(result, evalcache.Deferred)
print(result.compute())
```

On the first run, EvalCache evaluates and stores both operations. A fresh
process can restore their results from `.evalcache` when their operation
identity and arguments have not changed.

The default serializer uses pickle. Only open cache directories trusted by the
current user.

## Operation identity

By default, EvalCache derives an operation id from the function's module and
qualified name and derives a version from its Python implementation. For
long-lived caches, explicit identity makes invalidation intentional:

```python
@evalcache.operation(
    operation_id="my-project.build-mesh",
    operation_version="3",
    result=Mesh,
)
def build_mesh(source: Source) -> Mesh:
    ...
```

Keep `operation_id` stable while the operation retains the same meaning.
Increment `operation_version` when old cached results must no longer be used.
A return annotation normally supplies the result contract; `result=` can
instead accept a runtime type or a `ResultSpec` with a validator or custom
serializer.

Domain arguments must have deterministic identities. Register an encoder with
`HashRegistry` or implement `__evalcache_key__() -> bytes`:

```python
hashes = evalcache.HashRegistry()
hashes.register(Source, lambda source: source.digest.encode("ascii"))

@evalcache.operation(hash_registry=hashes)
def convert(source: Source) -> Mesh:
    ...
```

See [advanced_decorators.py](expers/advanced_decorators.py) for operation
versions, validation, domain hashing, progress events, and non-cacheable
operations.

## Policies and explicit evaluators

Module-level `@evalcache.operation` uses the default evaluator at call time.
`configure()` replaces its global policies without redecorating functions.
For libraries or isolated jobs, own the evaluator explicitly:

```python
evaluator = evalcache.Evaluator(
    cache_store=evalcache.DirectoryCacheStore(".evalcache"),
    cache_policy=evalcache.CachePolicy(namespace="geometry"),
)

@evaluator.operation
def triangulate(shape: Shape) -> Mesh:
    ...
```

`using_evaluator()` temporarily changes the default evaluator. Deferred
values owned by different evaluators cannot be mixed in one graph.

`CachePolicy` controls persistent reads, writes, namespaces, and corrupt
record recovery. In-memory reuse within an evaluator remains enabled even when
`CachePolicy.disabled()` disables persistent caching.

## Composing Deferred values

Arguments may contain other Deferred values inside lists, tuples, sets,
frozensets, and mappings. Operators with unambiguous lazy semantics create new
expression nodes without computing their operands:

```python
@evalcache.operation
def load_values() -> tuple[int, ...]:
    return (6, -4, 3)

values = load_values()
result = 10 + values[0] * 2 - abs(values[1])
assert result.compute() == 18
```

Unary `+`, `-`, `abs`, and `~` are supported, together with arithmetic,
matrix, bitwise, shift, reflected binary operators, and indexing. Comparisons,
truth testing, and implicit iteration require an explicit `.compute()`.

See [expression_tree.py](expers/expression_tree.py) and
[operators.py](expers/operators.py).

## File artifacts

A file-producing operation can return immutable contents while leaving the
destination path outside expression identity:

```python
@evalcache.operation(
    operation_id="my-project.render-report",
    operation_version="1",
    result=evalcache.file_artifact_result(),
)
def render_report(value: int) -> evalcache.FileArtifact:
    return evalcache.FileArtifact(
        name="report.txt",
        data=("result={}\n".format(value)).encode("utf-8"),
        media_type="text/plain",
    )

report = render_report(42)
report.materialize("first.txt")
report.materialize("second.txt")
```

`FileArtifact.from_path()` snapshots a backend that can only produce a file.
`materialize()` atomically replaces the selected destination. The current
serializer stores artifact bytes inside the cache record.

See [file_artifact.py](expers/file_artifact.py).

## Low-level API

Decorators are the normal entry point. Applications that need explicit domain
handles may construct `Expression[T]` values and submit or evaluate them with
`Evaluator`. Storage and serialization are replaceable through the
`CacheStore` and `Serializer` protocols; `MemoryCacheStore`,
`DirectoryCacheStore`, and `MappingCacheStore` are included.

## Original Lazy API

The original implementation remains available under `evalcache.legacy`:

```python
from evalcache.legacy import DirCache, Lazy

lazy = Lazy(cache=DirCache(".evalcache"))

@lazy
def calculate(value):
    return value * 2

assert calculate(21).unlazy() == 42
```

The historical top-level imports remain as compatibility aliases, but new code
should use `@evalcache.operation`. See [Legacy API and migration](docs/legacy.md)
and the [legacy examples](expers/legacy/).

## Further reading

- [Дисковое кэширование деревьев ленивых вычислений](https://habr.com/post/422937/)
- [Executable examples](expers/)

## License

EvalCache is distributed under the [MIT License](LICENSE).

Contact: mirmik (mirmikns@yandex.ru)
