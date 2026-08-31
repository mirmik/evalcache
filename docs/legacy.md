# Legacy API and migration

The original `Lazy`, `LazyObject`, `LazyFile`, `Memoize`, and dict-like
directory caches live in `evalcache.legacy`. Their former module and top-level
imports remain as compatibility shims.

## Original API

```python
from evalcache.legacy import DirCache, Lazy

lazy = Lazy(cache=DirCache(".evalcache"))

@lazy
def calculate(value):
    return value * 2

value = calculate(21).unlazy()
```

## Migrating a decorator

```python
import evalcache

evalcache.configure(
    cache_store=evalcache.DirectoryCacheStore(".evalcache"),
)

@evalcache.operation
def calculate(value: int) -> int:
    return value * 2

value = calculate(21).compute()
```

The two cache formats are independent. A migration starts with a fresh cache.

Main differences:

- decorated calls return `Deferred[T]`;
- cache policy belongs to an `Evaluator`, not an individual lazy object;
- operation identity and result serialization are explicit extension points;
- unsupported implicit Python behavior requires `.compute()`;
- file results use immutable `FileArtifact` contents and explicit
  materialization paths.

`legacy_expression()` can temporarily expose an existing `LazyObject` graph
as one opaque, non-cacheable expression leaf. It is intended for staged
migrations, not for new computation graphs.
