# coding: utf-8

from evalcache.dircache import DirCache
from evalcache.dircache_v2 import DirCache_v2
from evalcache.lazy import Lazy, LazyObject, LazyHash, Memoize
from evalcache.lazy import unlazy as _legacy_unlazy
from evalcache.lazy import unlazy_if_need as _legacy_unlazy_if_need
from evalcache.lazy import encache, decache, nocache, print_tree
from evalcache.lazyfile import LazyFile

from evalcache.v2 import (
    Artifact,
    CachePolicy,
    CacheRecord,
    CacheRecordError,
    CacheStore,
    Deferred,
    EvaluationEvent,
    EvaluationEventKind,
    EvaluationMode,
    Evaluator,
    Expression,
    ExpressionError,
    FileArtifact,
    FileArtifactSerializer,
    HashRegistry,
    HashingError,
    MappingCacheStore,
    MemoryCacheStore,
    Operation,
    PickleSerializer,
    ProgressHook,
    ResultSpec,
    ResultTypeError,
    SerializedValue,
    Serializer,
    configure,
    file_artifact_result,
    get_default_evaluator,
    legacy_expression,
    operation,
    set_default_evaluator,
    using_evaluator,
)

from evalcache.util import select, map, filter, reduce


def unlazy(obj, debug=False):
    if isinstance(obj, Deferred):
        return obj.compute()
    return _legacy_unlazy(obj, debug=debug)


def unlazy_if_need(obj):
    if isinstance(obj, Deferred):
        return obj.compute()
    return _legacy_unlazy_if_need(obj)
