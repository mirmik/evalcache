"""Compatibility imports for the former experimental evalcache.v2 module.

The expression API is now the main evalcache API. New code should import these
names directly from evalcache.
"""

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
