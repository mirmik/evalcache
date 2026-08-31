# EvalCache readiness for the ZenCad typed migration

- Date: 2026-08-31
- EvalCache branch: `v2`
- ZenCad branch: `feature/migration`
- Status: functionally viable; three EvalCache API refinements recommended
  before the public ZenCad rewrite

## Purpose

This audit checks whether the current decorator-first EvalCache is sufficient
to replace ZenCad's original `LazyObject` architecture without losing the
explicit domain types proven by ZenCad's private typed implementation.

The desired boundary is:

- EvalCache operations always return `Deferred[T]`;
- ZenCad users see stable domain handles such as `Solid`, `Curve`,
  `Scalar`, and `MeshData`;
- a ZenCad handle contains either a resolved immutable value or an EvalCache
  `Expression[T]`;
- evaluation mode and cache policy never change the visible ZenCad type.

## Verified state

The private `zencad._typed` implementation already proves the important
functional contracts:

- typed topology, value, transform, curve, surface, boundary, and mesh handles
  can contain EvalCache expressions without inheriting from `LazyObject`;
- `ResultSpec` validators preserve truthful runtime result types;
- ZenCad's serializers use `Artifact` and `SerializedValue` to store BREP,
  curve, surface, mesh, transform, and structured numeric results;
- immediate/deferred evaluation and cache on/off retain the same public handle
  classes;
- immutable ZenCad value snapshots expose deterministic
  `__evalcache_key__()` implementations;
- fresh evaluators and fresh processes can reuse persistent typed results.

The experimental layer still calls `Runtime._expression(...)` manually for
nearly every operation. It passes the backend callable, `ResultSpec`,
`operation_id`, version, and operands, then explicitly wraps the resulting
`Expression` in the appropriate domain handle. This works, but it is the
main source of boilerplate that the public rewrite should remove.

## Verification results

The ZenCad migration branch was tested against the current local EvalCache
checkout rather than the older installed package.

- A direct smoke test constructed a deferred typed `Solid`, retained an
  `Expression` internally, and evaluated its mass correctly.
- 29 representative typed tests and 58 subtests passed.
- The complete headless runner's isolated groups passed 3/3 and 13/13 tests.
- Of the main 351 discovered tests, 348 passed, one was skipped, and two
  failed because their settings assertions assume POSIX paths on Windows:
  one expects `XDG_CONFIG_HOME` to control the Windows settings location,
  and one requires an absolute path to start with `/`.
- The ZenCad working tree remained clean after the audit.

The two failures are settings-test portability issues and are unrelated to
EvalCache expression, decorator, serialization, or cache behavior.

## What is already sufficient

### Domain result model

EvalCache should not manufacture ZenCad objects. A decorated backend operation
returns `Deferred[ResolvedT]`; a ZenCad adapter takes its `expression` and
constructs a domain handle. This preserves both libraries' responsibilities:

```text
pure resolved backend
        |
        v
EvalCache Operation -> Deferred[ResolvedT]
        |
        v
ZenCad adapter -> Solid / Curve / Scalar / other domain handle
```

ZenCad's existing `Handle[ResolvedT]` and `ResultSpec` families already
provide the necessary result adapters and serializers.

### Persistent storage

`DirectoryCacheStore` can replace
`MappingCacheStore(DirCache_v2(...))`. ZenCad should continue to own:

- selection and permission hardening of its shared per-user cache directory;
- environment, settings, and process-level cache configuration;
- the ZenCad cache namespace and schema invalidation policy.

Disabling persistent caching maps directly to `CachePolicy.disabled()`;
the legacy `DisabledCache` mapping is unnecessary for the new runtime.

### File boundaries

The typed implementation currently treats file operations sensibly:

- BREP and SVG imports read or snapshot contents at the explicit API boundary;
- BREP, STL, and SVG exports write immediately to the requested path;
- font registration remains an immediate process-wide side effect;
- operations that depend on process-global font state are non-cacheable.

File exports should not be decorated merely to avoid repeating a side effect:
on a cache hit, the requested destination would otherwise not be written.
`FileArtifact` is available when an operation genuinely produces reusable
immutable contents that may be materialized to several destinations.

### Custom serialization

ZenCad's BREP and binary serializers fit the EvalCache contracts directly.
They avoid pickling mutable native OCP values and validate artifact family,
payload marker, and result type during restoration.

The outer `DirectoryCacheStore` record is still pickle-based and therefore
must remain in a per-user trusted directory. The current ZenCad cache
configuration already enforces that trust boundary.

## Required refinements before the mass rewrite

### 1. Canonical operation arguments

Equivalent calls do not currently always share expression identity.
Diagnostic checks confirmed:

```text
{"a": 1, "b": 2} versus {"b": 2, "a": 1}  -> different digests
f(left=1, right=2) versus f(right=2, left=1) -> different digests
```

This is undesirable for a decorator-first cache and will create avoidable
misses in user scripts.

Required behavior:

- sort frozen mapping entries by their deterministic encoded representation;
- sort keyword arguments by parameter name;
- at the `Operation` boundary, normalize calls with
  `inspect.signature(function).bind(...)`;
- apply default values so `f(1)`, `f(value=1)`, and an explicitly supplied
  default have one identity when they are semantically the same call;
- retain the low-level `Expression.create()` API for callers that
  intentionally provide an exact argument structure.

### 2. Typed decorator signatures

EvalCache ships `py.typed`, but its decorators currently erase parameter
types:

- `evalcache.operation(...)` is annotated as returning `Any`;
- `Operation.__call__` accepts `*args: Any, **kwargs: Any`;
- only the result type variable is retained.

ZenCad already uses strict mypy checks, so the public rewrite should not build
on decorators that hide invalid calls.

Required behavior:

- introduce `ParamSpec` for operation parameters;
- model operations as `Operation[P, T]`;
- make `Operation.__call__(*args: P.args, **kwargs: P.kwargs)` return
  `Deferred[T]`;
- add overloads for bare and configured forms of `operation`,
  `Evaluator.operation`, and evaluator-as-decorator usage;
- retain the original function signature for introspection and static tools.

Result inference also needs to recognize parameterized runtime annotations.
For example, a function returning `list[int]` currently receives a dynamic
`object` result contract. At minimum, inference should use
`typing.get_origin()` for standard containers and support simple unions of
runtime-checkable types. Explicit `ResultSpec` remains the correct choice for
ZenCad's serialized result families.

### 3. Reusable operations with a selected evaluator

ZenCad declares each pure backend operation once, but different `Runtime`
instances own different evaluators and policies.

Current choices are awkward:

- module-level operations consult mutable global evaluator state;
- `@evaluator.operation` permanently binds the definition to one evaluator;
- constructing every operation separately for every runtime repeats metadata;
- calling `Evaluator.submit()` manually recreates the boilerplate that the
  decorators were meant to remove.

EvalCache should expose an explicit binding operation, for example:

```python
deferred = box_operation.bind(runtime.evaluator)(size, center)
```

The exact spelling may instead be `for_evaluator()`, but its contract should
be:

- reuse one immutable `Operation[P, T]` definition;
- select an evaluator for one bound callable or invocation;
- return an ordinary `Deferred[T]`;
- avoid process-global evaluator mutation;
- preserve evaluator ownership checks for nested deferred values.

ZenCad can then implement its own typed adapter decorator:

```python
@domain_operation(box_operation, returns=Solid)
def box(self, x, y, z, center=False):
    size = normalize_box_size(self, x, y, z)
    return size._state, center
```

Conceptually, the adapter performs:

```python
operands = prepare_arguments(runtime, *args, **kwargs)
deferred = operation.bind(runtime.evaluator)(*operands)
return handle_type._from_state(runtime, deferred.expression)
```

EvalCache still returns `Deferred`; only ZenCad knows how to construct a
`Solid` or another domain handle.

## Follow-up needed before public cutover

### Graph introspection for progress reporting

`EvaluationEvent` is sufficient for live start, hit, store, finish, and
error notifications. It is not sufficient to reproduce the old runner's
`toload` and `toeval` totals because there is no public way to traverse an
expression's dependencies or plan cache work before evaluation.

This does not block the core domain rewrite. Before public cutover, choose one:

- add `Expression.dependencies()` and let ZenCad maintain progress totals;
- add an `Evaluator.plan(expression)` API that returns graph and anticipated
  cache work;
- intentionally switch the UI to indeterminate progress and event labels.

The first or second option is preferable to making ZenCad inspect EvalCache's
private argument-node classes.

### Cache configuration cutover

The private typed `Runtime` currently defaults to
`MappingCacheStore(lazy.cache)`, which keeps the new path coupled to the
legacy global `Lazy` object.

During the public rewrite:

- construct `DirectoryCacheStore` directly from ZenCad's resolved cache
  configuration;
- let the ZenCad runtime own or replace its evaluator when configuration
  changes;
- update the dependency to the chosen EvalCache 2 prerelease or release;
- replace `from evalcache.v2 import ...` with top-level imports;
- keep a distinct ZenCad namespace so schema changes can invalidate the whole
  disposable cache intentionally.

## Recommended implementation order

1. Fix mapping, keyword, and decorated-call canonicalization in EvalCache.
2. Add `ParamSpec`-preserving decorator types and container result inference.
3. Add explicit reusable-operation binding to a selected evaluator.
4. Prototype one ZenCad `@domain_operation` adapter for `box`, a scalar
   operation, and one method on `Shape`.
5. Replace the private runtime's legacy mapping store with
   `DirectoryCacheStore`.
6. Move operation definitions beside their pure resolved backends and reduce
   `Runtime` to policy ownership, normalization, and public orchestration.
7. Decide the progress-planning contract before the managed-runner cutover.
8. Perform the public ZenCad API switch atomically, as required by the existing
   typed-domain migration plan.

## Conclusion

There is no missing computational, persistence, artifact, or serialization
primitive preventing the ZenCad migration. The current EvalCache is already
compatible with the proven typed graph.

The mass rewrite should wait for three focused refinements: canonical
arguments, statically typed decorators, and reusable operation binding to a
chosen evaluator. Once those are present, ZenCad can replace the repeated
manual `_expression(...)` and `_from_state(...)` pairs with a small domain
adapter decorator while preserving explicit public types and EvalCache's
`Deferred` contract.
