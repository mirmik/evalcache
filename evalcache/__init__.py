"""Decorator-first caching of reusable expression graphs."""

import importlib

from evalcache.artifacts import (
    FileArtifact,
    FileArtifactSerializer,
    file_artifact_result,
)
from evalcache.cache import (
    Artifact,
    CachePolicy,
    CacheRecord,
    CacheStore,
    DirectoryCacheStore,
    MappingCacheStore,
    MemoryCacheStore,
    PickleSerializer,
    ResultSpec,
    SerializedValue,
    Serializer,
)
from evalcache.errors import (
    CacheRecordError,
    ExpressionError,
    HashingError,
    ResultTypeError,
)
from evalcache.evaluation import (
    EvaluationEvent,
    EvaluationEventKind,
    EvaluationMode,
    Evaluator,
    ProgressHook,
)
from evalcache.expression import Deferred, Expression
from evalcache.hashing import HashRegistry
from evalcache.operation import (
    Operation,
    configure,
    get_default_evaluator,
    legacy_expression,
    operation,
    set_default_evaluator,
    using_evaluator,
)

_LEGACY_EXPORTS = {
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
}
_LEGACY_MODULES = {
    "dircache",
    "dircache_v2",
    "funcarg",
    "lazy",
    "lazyfile",
    "util",
}


def __getattr__(name):
    """Resolve original API names without loading legacy code on normal import."""

    if name == "legacy":
        return importlib.import_module("evalcache.legacy")
    if name in _LEGACY_MODULES:
        return importlib.import_module("evalcache." + name)
    if name in _LEGACY_EXPORTS:
        value = getattr(importlib.import_module("evalcache.legacy"), name)
        globals()[name] = value
        return value
    raise AttributeError("module 'evalcache' has no attribute {!r}".format(name))


def unlazy(obj, debug=False):
    """Compute a Deferred or unwrap an original LazyObject."""

    if isinstance(obj, Deferred):
        return obj.compute()
    from evalcache.legacy import unlazy as legacy_unlazy

    return legacy_unlazy(obj, debug=debug)


def unlazy_if_need(obj):
    if isinstance(obj, Deferred):
        return obj.compute()
    from evalcache.legacy import unlazy_if_need as legacy_unlazy_if_need

    return legacy_unlazy_if_need(obj)


__all__ = [
    "Artifact",
    "CachePolicy",
    "CacheRecord",
    "CacheRecordError",
    "CacheStore",
    "Deferred",
    "DirectoryCacheStore",
    "EvaluationEvent",
    "EvaluationEventKind",
    "EvaluationMode",
    "Evaluator",
    "Expression",
    "ExpressionError",
    "FileArtifact",
    "FileArtifactSerializer",
    "HashRegistry",
    "HashingError",
    "MappingCacheStore",
    "MemoryCacheStore",
    "Operation",
    "PickleSerializer",
    "ProgressHook",
    "ResultSpec",
    "ResultTypeError",
    "SerializedValue",
    "Serializer",
    "configure",
    "file_artifact_result",
    "get_default_evaluator",
    "legacy_expression",
    "operation",
    "set_default_evaluator",
    "using_evaluator",
]
