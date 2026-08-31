"""Typed expressions with explicit and decorator-first evaluation APIs.

This module is intentionally independent from application domain types.  It
does not imitate the Python interface of a value that has not been computed;
decorated functions return :class:`Deferred`, while domain libraries may keep
:class:`Expression` inside their own stable public handles.  The original
``LazyObject`` API remains available from :mod:`evalcache.lazy`.
"""

from __future__ import annotations

from contextlib import contextmanager
import functools
import hashlib
import inspect
import operator
import os
import pickle
import struct
import tempfile
import types
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    MutableMapping,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    get_type_hints,
    runtime_checkable,
)


T = TypeVar("T")


class ExpressionError(Exception):
    """Base exception for the typed expression kernel."""


class HashingError(ExpressionError, TypeError):
    """A value cannot participate in deterministic expression identity."""


class ResultTypeError(ExpressionError, TypeError):
    """An operation produced a value outside its declared result contract."""


class CacheRecordError(ExpressionError):
    """A persistent cache record is invalid or incompatible."""


class EvaluationMode(str, Enum):
    DEFERRED = "deferred"
    IMMEDIATE = "immediate"


@dataclass(frozen=True)
class CachePolicy:
    """Persistent cache policy; in-memory DAG reuse is always enabled."""

    read: bool = True
    write: bool = True
    namespace: str = "evalcache-v2"
    recover_corrupt: bool = True

    def __post_init__(self) -> None:
        if not self.namespace:
            raise ValueError("cache namespace must not be empty")

    @classmethod
    def disabled(cls, namespace: str = "evalcache-v2") -> "CachePolicy":
        return cls(read=False, write=False, namespace=namespace)

    @property
    def enabled(self) -> bool:
        return self.read or self.write


@dataclass(frozen=True)
class Artifact:
    """A named binary artifact emitted by a result serializer."""

    name: str
    data: bytes
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        _validate_artifact_fields(self.name, self.data, self.media_type)


def _validate_artifact_fields(name: str, data: bytes, media_type: str) -> None:
    if not isinstance(name, str):
        raise TypeError("artifact name must be str")
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        raise ValueError("artifact name must be a non-empty basename")
    if not isinstance(data, bytes):
        raise TypeError("artifact data must be bytes")
    if not isinstance(media_type, str):
        raise TypeError("artifact media_type must be str")
    if not media_type:
        raise ValueError("artifact media_type must not be empty")


@dataclass(frozen=True)
class SerializedValue:
    payload: bytes
    artifacts: Tuple[Artifact, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.payload, bytes):
            raise TypeError("serialized payload must be bytes")
        names = [artifact.name for artifact in self.artifacts]
        if len(names) != len(set(names)):
            raise ValueError("artifact names must be unique")


@runtime_checkable
class Serializer(Protocol[T]):
    serializer_id: str

    def dumps(self, value: T) -> SerializedValue: ...

    def loads(self, value: SerializedValue) -> T: ...


class PickleSerializer(Generic[T]):
    """Default serializer for trusted cache directories.

    Pickle is deliberately explicit in the result metadata.  Applications
    that cross a trust boundary should provide a non-executable serializer.
    """

    serializer_id = "python.pickle.v5"

    def dumps(self, value: T) -> SerializedValue:
        return SerializedValue(pickle.dumps(value, protocol=5))

    def loads(self, value: SerializedValue) -> T:
        return cast(T, pickle.loads(value.payload))


_DEFAULT_SERIALIZER: PickleSerializer[Any] = PickleSerializer()
ExpectedType = Union[Type[Any], Tuple[Type[Any], ...]]


@dataclass(frozen=True)
class ResultSpec(Generic[T]):
    """Runtime metadata and serialization contract for ``Expression[T]``."""

    type_id: str
    expected_type: ExpectedType
    serializer: Serializer[T] = field(
        default=cast(Serializer[T], _DEFAULT_SERIALIZER),
        compare=False,
        repr=False,
    )
    validator: Optional[Callable[[T], bool]] = field(
        default=None,
        compare=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not self.type_id:
            raise ValueError("result type_id must not be empty")
        if not isinstance(self.expected_type, (type, tuple)):
            raise TypeError("expected_type must be a type or tuple of types")
        if isinstance(self.expected_type, tuple):
            if not self.expected_type or not all(
                isinstance(item, type) for item in self.expected_type
            ):
                raise TypeError("expected_type tuple must contain types")
        if not getattr(self.serializer, "serializer_id", ""):
            raise TypeError("serializer must declare serializer_id")

    @classmethod
    def for_type(
        cls,
        expected_type: Type[T],
        *,
        type_id: Optional[str] = None,
        serializer: Optional[Serializer[T]] = None,
        validator: Optional[Callable[[T], bool]] = None,
    ) -> "ResultSpec[T]":
        resolved_id = type_id or (
            expected_type.__module__ + "." + expected_type.__qualname__
        )
        return cls(
            type_id=resolved_id,
            expected_type=expected_type,
            serializer=serializer or cast(Serializer[T], _DEFAULT_SERIALIZER),
            validator=validator,
        )

    def validate(self, value: Any, operation_id: str) -> T:
        if not isinstance(value, self.expected_type):
            expected = _expected_type_name(self.expected_type)
            actual = type(value).__module__ + "." + type(value).__qualname__
            raise ResultTypeError(
                "operation {!r} declared {} but produced {}".format(
                    operation_id,
                    expected,
                    actual,
                )
            )
        typed_value = cast(T, value)
        if self.validator is not None and not self.validator(typed_value):
            raise ResultTypeError(
                "operation {!r} produced a value rejected by {}".format(
                    operation_id,
                    self.type_id,
                )
            )
        return typed_value


@dataclass(frozen=True)
class FileArtifact:
    """Immutable file contents, independent from a materialization path."""

    name: str
    data: bytes
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        _validate_artifact_fields(self.name, self.data, self.media_type)

    @classmethod
    def from_path(
        cls,
        path: Union[str, os.PathLike[str]],
        *,
        name: Optional[str] = None,
        media_type: str = "application/octet-stream",
    ) -> "FileArtifact":
        """Snapshot an existing file into an immutable artifact."""

        source = Path(path).expanduser()
        return cls(
            name=source.name if name is None else name,
            data=source.read_bytes(),
            media_type=media_type,
        )

    @property
    def content_digest(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    def __evalcache_key__(self) -> bytes:
        return _pack(
            b"file-artifact-v1",
            self.name.encode("utf-8"),
            self.media_type.encode("utf-8"),
            bytes.fromhex(self.content_digest),
        )

    def materialize(
        self,
        path: Union[str, os.PathLike[str]],
    ) -> Path:
        """Atomically write this artifact to an explicit destination path."""

        destination = Path(path).expanduser()
        parent = destination.parent
        if not parent.is_dir():
            raise FileNotFoundError(
                "artifact destination directory does not exist: {}".format(parent)
            )
        if destination.is_dir():
            raise IsADirectoryError(str(destination))

        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".{}-".format(destination.name),
            suffix=".tmp",
            dir=str(parent),
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self.data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, str(destination))
        finally:
            try:
                os.remove(temporary_path)
            except FileNotFoundError:
                pass
        return destination


_FILE_ARTIFACT_PAYLOAD = b"evalcache.file-artifact\x00v1"


class FileArtifactSerializer:
    """Store FileArtifact contents through SerializedValue artifacts."""

    serializer_id = "evalcache.file-artifact.v1"

    def dumps(self, value: FileArtifact) -> SerializedValue:
        if not isinstance(value, FileArtifact):
            raise TypeError("file artifact serializer requires FileArtifact")
        return SerializedValue(
            payload=_FILE_ARTIFACT_PAYLOAD,
            artifacts=(
                Artifact(
                    name=value.name,
                    data=value.data,
                    media_type=value.media_type,
                ),
            ),
        )

    def loads(self, value: SerializedValue) -> FileArtifact:
        if value.payload != _FILE_ARTIFACT_PAYLOAD:
            raise ValueError("unsupported file artifact cache payload")
        if len(value.artifacts) != 1:
            raise ValueError("file artifact cache record must contain one artifact")
        artifact = value.artifacts[0]
        return FileArtifact(
            name=artifact.name,
            data=artifact.data,
            media_type=artifact.media_type,
        )


_FILE_ARTIFACT_SERIALIZER = FileArtifactSerializer()


def file_artifact_result(
    *,
    type_id: str = "evalcache.FileArtifact.v1",
    validator: Optional[Callable[[FileArtifact], bool]] = None,
) -> ResultSpec[FileArtifact]:
    """Return the built-in result contract for materializable files."""

    return ResultSpec.for_type(
        FileArtifact,
        type_id=type_id,
        serializer=_FILE_ARTIFACT_SERIALIZER,
        validator=validator,
    )


def _expected_type_name(expected_type: ExpectedType) -> str:
    if isinstance(expected_type, tuple):
        return " | ".join(
            item.__module__ + "." + item.__qualname__ for item in expected_type
        )
    return expected_type.__module__ + "." + expected_type.__qualname__


@dataclass(frozen=True)
class CacheRecord:
    schema: int
    result_type_id: str
    serializer_id: str
    value: SerializedValue


@runtime_checkable
class CacheStore(Protocol):
    def get(self, key: str) -> Optional[CacheRecord]: ...

    def put(self, key: str, record: CacheRecord) -> None: ...

    def delete(self, key: str) -> None: ...


class MemoryCacheStore:
    def __init__(self) -> None:
        self.records: Dict[str, CacheRecord] = {}

    def get(self, key: str) -> Optional[CacheRecord]:
        return self.records.get(key)

    def put(self, key: str, record: CacheRecord) -> None:
        self.records[key] = record

    def delete(self, key: str) -> None:
        self.records.pop(key, None)


class MappingCacheStore:
    """Adapter for legacy dict-like stores, including ``DirCache_v2``."""

    def __init__(self, mapping: MutableMapping[str, Any]) -> None:
        self.mapping = mapping

    def get(self, key: str) -> Optional[CacheRecord]:
        if key not in self.mapping:
            return None
        record = self.mapping[key]
        if not isinstance(record, CacheRecord):
            raise CacheRecordError(
                "cache key {} does not contain an evalcache v2 record".format(key)
            )
        return record

    def put(self, key: str, record: CacheRecord) -> None:
        self.mapping[key] = record

    def delete(self, key: str) -> None:
        try:
            del self.mapping[key]
        except KeyError:
            pass


HashEncoder = Callable[[Any], bytes]


class HashRegistry:
    """Deterministic encoders for immutable literal values."""

    def __init__(self) -> None:
        self._encoders: Dict[Type[Any], Tuple[str, HashEncoder]] = {}

    def register(
        self,
        value_type: Type[Any],
        encoder: HashEncoder,
        *,
        type_id: Optional[str] = None,
    ) -> None:
        resolved_id = type_id or (value_type.__module__ + "." + value_type.__qualname__)
        self._encoders[value_type] = (resolved_id, encoder)

    def encode(self, value: Any) -> bytes:
        if value is None:
            return b"none"
        if type(value) is bool:
            return b"bool:1" if value else b"bool:0"
        if type(value) is int:
            return _pack(b"int", str(value).encode("ascii"))
        if type(value) is float:
            return _pack(b"float", struct.pack(">d", value))
        if type(value) is str:
            return _pack(b"str", value.encode("utf-8"))
        if type(value) is bytes:
            return _pack(b"bytes", value)
        if isinstance(value, Enum):
            enum_type = type(value)
            return _pack(
                b"enum",
                (enum_type.__module__ + "." + enum_type.__qualname__).encode("utf-8"),
                value.name.encode("utf-8"),
            )

        for value_type in type(value).__mro__:
            registered = self._encoders.get(value_type)
            if registered is not None:
                type_id, encoder = registered
                payload = encoder(value)
                if not isinstance(payload, bytes):
                    raise HashingError(
                        "hash encoder for {} must return bytes".format(type_id)
                    )
                return _pack(b"custom", type_id.encode("utf-8"), payload)

        hook = getattr(value, "__evalcache_key__", None)
        if hook is not None:
            if not callable(hook):
                raise HashingError("__evalcache_key__ must be callable")
            payload = hook()
            if not isinstance(payload, bytes):
                raise HashingError("__evalcache_key__ must return bytes")
            value_type = type(value)
            return _pack(
                b"hook",
                (value_type.__module__ + "." + value_type.__qualname__).encode("utf-8"),
                payload,
            )

        value_type = type(value)
        raise HashingError(
            "no deterministic hash encoder for {}.{}".format(
                value_type.__module__,
                value_type.__qualname__,
            )
        )


@dataclass(frozen=True)
class _LiteralArgument:
    value: Any = field(compare=False, repr=False)
    encoded: bytes


@dataclass(frozen=True)
class _SequenceArgument:
    kind: str
    items: Tuple["_Argument", ...]


@dataclass(frozen=True)
class _MappingArgument:
    items: Tuple[Tuple["_Argument", "_Argument"], ...]


_Argument = Union[
    "Expression[Any]",
    _LiteralArgument,
    _SequenceArgument,
    _MappingArgument,
]


def _freeze_argument(value: Any, registry: HashRegistry) -> _Argument:
    if isinstance(value, Deferred):
        return value.expression
    if isinstance(value, Expression):
        return value
    if isinstance(value, list):
        return _SequenceArgument(
            "list",
            tuple(_freeze_argument(item, registry) for item in value),
        )
    if isinstance(value, tuple):
        return _SequenceArgument(
            "tuple",
            tuple(_freeze_argument(item, registry) for item in value),
        )
    if isinstance(value, (set, frozenset)):
        items = [_freeze_argument(item, registry) for item in value]
        items.sort(key=_argument_bytes)
        return _SequenceArgument(
            "frozenset" if isinstance(value, frozenset) else "set",
            tuple(items),
        )
    if isinstance(value, Mapping):
        return _MappingArgument(
            tuple(
                (
                    _freeze_argument(key, registry),
                    _freeze_argument(item, registry),
                )
                for key, item in value.items()
            )
        )
    return _LiteralArgument(value, registry.encode(value))


def _argument_bytes(argument: _Argument) -> bytes:
    if isinstance(argument, Expression):
        return _pack(b"expression", argument.digest.encode("ascii"))
    if isinstance(argument, _LiteralArgument):
        return _pack(b"literal", argument.encoded)
    if isinstance(argument, _SequenceArgument):
        return _pack(
            b"sequence",
            argument.kind.encode("ascii"),
            *(_argument_bytes(item) for item in argument.items),
        )
    if isinstance(argument, _MappingArgument):
        return _pack(
            b"mapping",
            *(
                _pack(b"item", _argument_bytes(key), _argument_bytes(value))
                for key, value in argument.items
            ),
        )
    raise AssertionError("unknown argument node")


def _pack(tag: bytes, *parts: bytes) -> bytes:
    result = bytearray(tag)
    result.extend(b"\x00")
    for part in parts:
        result.extend(len(part).to_bytes(8, "big"))
        result.extend(part)
    return bytes(result)


def _code_constant_bytes(value: Any, registry: HashRegistry) -> bytes:
    if isinstance(value, types.CodeType):
        return _code_bytes(value, registry)
    if isinstance(value, tuple):
        return _pack(
            b"constant-tuple",
            *(_code_constant_bytes(item, registry) for item in value),
        )
    if isinstance(value, frozenset):
        items = sorted(_code_constant_bytes(item, registry) for item in value)
        return _pack(b"constant-frozenset", *items)
    return registry.encode(value)


def _code_bytes(code: types.CodeType, registry: HashRegistry) -> bytes:
    return _pack(
        b"python-code-v1",
        code.co_code,
        _pack(
            b"constants",
            *(_code_constant_bytes(constant, registry) for constant in code.co_consts),
        ),
        _pack(b"names", *(name.encode("utf-8") for name in code.co_names)),
        _pack(
            b"varnames",
            *(name.encode("utf-8") for name in code.co_varnames),
        ),
        _pack(
            b"freevars",
            *(name.encode("utf-8") for name in code.co_freevars),
        ),
        str(code.co_argcount).encode("ascii"),
        str(code.co_kwonlyargcount).encode("ascii"),
    )


def _callable_identity(
    operation: Callable[..., Any],
    registry: HashRegistry,
) -> Tuple[str, str]:
    module = getattr(operation, "__module__", type(operation).__module__)
    qualname = getattr(operation, "__qualname__", type(operation).__qualname__)
    operation_id = module + "." + qualname
    code = getattr(operation, "__code__", None)
    if code is None:
        version_source = _pack(b"callable-name", operation_id.encode("utf-8"))
    else:
        parts = [_code_bytes(code, registry)]
        defaults = getattr(operation, "__defaults__", None) or ()
        parts.append(
            _pack(
                b"defaults",
                *(_code_constant_bytes(value, registry) for value in defaults),
            )
        )
        keyword_defaults = getattr(operation, "__kwdefaults__", None) or {}
        parts.append(
            _pack(
                b"keyword-defaults",
                *(
                    _pack(
                        b"default",
                        key.encode("utf-8"),
                        _code_constant_bytes(value, registry),
                    )
                    for key, value in sorted(keyword_defaults.items())
                ),
            )
        )
        closure = getattr(operation, "__closure__", None) or ()
        parts.append(
            _pack(
                b"closure",
                *(
                    _code_constant_bytes(cell.cell_contents, registry)
                    for cell in closure
                ),
            )
        )
        version_source = _pack(b"python-callable-v1", *parts)
    return operation_id, hashlib.sha256(version_source).hexdigest()


@dataclass(frozen=True)
class Expression(Generic[T]):
    """Immutable, typed description of a pure computation."""

    operation: Callable[..., T] = field(compare=False, repr=False)
    operation_id: str
    operation_version: str
    result: ResultSpec[T] = field(compare=False)
    arguments: Tuple[_Argument, ...] = field(compare=False, repr=False)
    keyword_arguments: Tuple[Tuple[str, _Argument], ...] = field(
        compare=False,
        repr=False,
    )
    digest: str
    cacheable: bool = True

    @classmethod
    def create(
        cls,
        operation: Callable[..., T],
        *,
        result: ResultSpec[T],
        args: Iterable[Any] = (),
        kwargs: Optional[Mapping[str, Any]] = None,
        operation_id: Optional[str] = None,
        operation_version: Optional[str] = None,
        hash_registry: Optional[HashRegistry] = None,
        cacheable: bool = True,
    ) -> "Expression[T]":
        registry = hash_registry or HashRegistry()
        if operation_id is not None and operation_version is not None:
            resolved_id = operation_id
            resolved_version = operation_version
        else:
            default_id, default_version = _callable_identity(
                operation,
                registry,
            )
            resolved_id = operation_id or default_id
            resolved_version = operation_version or default_version
        if not resolved_id or not resolved_version:
            raise ValueError("operation identity and version must not be empty")

        frozen_args = tuple(_freeze_argument(value, registry) for value in args)
        frozen_kwargs = tuple(
            (name, _freeze_argument(value, registry))
            for name, value in (kwargs or {}).items()
        )
        digest_source = _pack(
            b"evalcache-expression-v2",
            resolved_id.encode("utf-8"),
            resolved_version.encode("utf-8"),
            result.type_id.encode("utf-8"),
            result.serializer.serializer_id.encode("utf-8"),
            b"cacheable:1" if cacheable else b"cacheable:0",
            _pack(b"args", *(_argument_bytes(arg) for arg in frozen_args)),
            _pack(
                b"kwargs",
                *(
                    _pack(
                        b"kwarg",
                        name.encode("utf-8"),
                        _argument_bytes(value),
                    )
                    for name, value in frozen_kwargs
                ),
            ),
        )
        return cls(
            operation=operation,
            operation_id=resolved_id,
            operation_version=resolved_version,
            result=result,
            arguments=frozen_args,
            keyword_arguments=frozen_kwargs,
            digest=hashlib.sha256(digest_source).hexdigest(),
            cacheable=cacheable,
        )


_DEFERRED_OPERATOR_RESULT = ResultSpec.for_type(
    object,
    type_id="evalcache.operator.dynamic-result.v1",
)


@dataclass(frozen=True, eq=False)
class Deferred(Generic[T]):
    """An expression bound to the evaluator that owns its policy and memory."""

    __hash__ = None

    evaluator: "Evaluator" = field(compare=False, repr=False)
    expression: Expression[T]

    @property
    def digest(self) -> str:
        return self.expression.digest

    @property
    def operation_id(self) -> str:
        return self.expression.operation_id

    def compute(self) -> T:
        return self.evaluator.evaluate(self.expression)

    def evaluate(self) -> T:
        return self.compute()

    def unlazy(self) -> T:
        """Compatibility spelling for the original decorator-first API."""

        return self.compute()

    def materialize(
        self,
        path: Union[str, os.PathLike[str]],
    ) -> Path:
        """Compute and materialize a FileArtifact result."""

        value = self.compute()
        if not isinstance(value, FileArtifact):
            raise TypeError(
                "Deferred.materialize requires a FileArtifact result"
            )
        return value.materialize(path)

    def _operator(
        self,
        name: str,
        function: Callable[..., Any],
        *args: Any,
    ) -> "Deferred[Any]":
        return self.evaluator.submit(
            function,
            result=_DEFERRED_OPERATOR_RESULT,
            args=args,
            operation_id="evalcache.operator." + name,
            operation_version="1",
        )

    def _unary_operator(
        self,
        name: str,
        function: Callable[[Any], Any],
    ) -> "Deferred[Any]":
        return self._operator(name, function, self)

    def _binary_operator(
        self,
        other: Any,
        name: str,
        function: Callable[[Any, Any], Any],
    ) -> "Deferred[Any]":
        return self._operator(name, function, self, other)

    def _reflected_operator(
        self,
        other: Any,
        name: str,
        function: Callable[[Any, Any], Any],
    ) -> "Deferred[Any]":
        return self._operator(name, function, other, self)

    def __pos__(self) -> "Deferred[Any]":
        return self._unary_operator("positive", operator.pos)

    def __neg__(self) -> "Deferred[Any]":
        return self._unary_operator("negative", operator.neg)

    def __abs__(self) -> "Deferred[Any]":
        return self._unary_operator("absolute", operator.abs)

    def __invert__(self) -> "Deferred[Any]":
        return self._unary_operator("invert", operator.invert)

    def __add__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "add", operator.add)

    def __radd__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "add", operator.add)

    def __sub__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "subtract", operator.sub)

    def __rsub__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "subtract", operator.sub)

    def __mul__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "multiply", operator.mul)

    def __rmul__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "multiply", operator.mul)

    def __truediv__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "true_divide", operator.truediv)

    def __rtruediv__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "true_divide", operator.truediv)

    def __floordiv__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "floor_divide", operator.floordiv)

    def __rfloordiv__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "floor_divide", operator.floordiv)

    def __mod__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "modulo", operator.mod)

    def __rmod__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "modulo", operator.mod)

    def __pow__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "power", operator.pow)

    def __rpow__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "power", operator.pow)

    def __matmul__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "matrix_multiply", operator.matmul)

    def __rmatmul__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(
            other,
            "matrix_multiply",
            operator.matmul,
        )

    def __and__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "and", operator.and_)

    def __rand__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "and", operator.and_)

    def __or__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "or", operator.or_)

    def __ror__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "or", operator.or_)

    def __xor__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "xor", operator.xor)

    def __rxor__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "xor", operator.xor)

    def __lshift__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "left_shift", operator.lshift)

    def __rlshift__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "left_shift", operator.lshift)

    def __rshift__(self, other: Any) -> "Deferred[Any]":
        return self._binary_operator(other, "right_shift", operator.rshift)

    def __rrshift__(self, other: Any) -> "Deferred[Any]":
        return self._reflected_operator(other, "right_shift", operator.rshift)

    def __getitem__(self, key: Any) -> "Deferred[Any]":
        return self._operator("getitem", operator.getitem, self, key)

    def __iter__(self) -> Iterator[Any]:
        raise TypeError(
            "Deferred is not implicitly iterable; call compute() explicitly"
        )

    def _unsupported_comparison(self) -> bool:
        raise TypeError(
            "Deferred comparisons are not supported; call compute() explicitly"
        )

    def __eq__(self, other: object) -> bool:
        return self._unsupported_comparison()

    def __ne__(self, other: object) -> bool:
        return self._unsupported_comparison()

    def __lt__(self, other: object) -> bool:
        return self._unsupported_comparison()

    def __le__(self, other: object) -> bool:
        return self._unsupported_comparison()

    def __gt__(self, other: object) -> bool:
        return self._unsupported_comparison()

    def __ge__(self, other: object) -> bool:
        return self._unsupported_comparison()

    def __bool__(self) -> bool:
        raise TypeError(
            "Deferred has no implicit truth value; call compute() explicitly"
        )


def _deferred_values(value: Any) -> Iterable[Deferred[Any]]:
    if isinstance(value, Deferred):
        yield value
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from _deferred_values(key)
            yield from _deferred_values(item)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _deferred_values(item)


def _require_owned_deferred(value: Any, evaluator: "Evaluator") -> None:
    for deferred in _deferred_values(value):
        if deferred.evaluator is not evaluator:
            raise ValueError("cannot mix Deferred values from different evaluators")


class EvaluationEventKind(str, Enum):
    START = "start"
    MEMORY_HIT = "memory_hit"
    CACHE_HIT = "cache_hit"
    CACHE_REJECTED = "cache_rejected"
    CACHE_STORE = "cache_store"
    FINISH = "finish"
    ERROR = "error"


@dataclass(frozen=True)
class EvaluationEvent:
    kind: EvaluationEventKind
    expression_digest: str
    operation_id: str
    cache_key: Optional[str] = None
    detail: Optional[str] = None


ProgressHook = Callable[[EvaluationEvent], None]
_MISSING = object()


class Evaluator:
    """Resolve typed expressions according to evaluation and cache policy."""

    def __init__(
        self,
        *,
        mode: EvaluationMode = EvaluationMode.DEFERRED,
        cache_policy: Optional[CachePolicy] = None,
        cache_store: Optional[CacheStore] = None,
        progress_hooks: Iterable[ProgressHook] = (),
    ) -> None:
        self.mode = EvaluationMode(mode)
        self.cache_policy = cache_policy or CachePolicy()
        self.cache_store = cache_store
        self.progress_hooks = tuple(progress_hooks)
        self._values: Dict[str, Any] = {}
        self._active: Dict[str, Expression[Any]] = {}

    def __call__(
        self,
        function: Optional[Callable[..., T]] = None,
        **options: Any,
    ) -> Any:
        """Use the evaluator itself as a decorator, as with the original Lazy."""

        return self.operation(function, **options)

    def expression(
        self,
        operation: Callable[..., T],
        *,
        result: ResultSpec[T],
        args: Iterable[Any] = (),
        kwargs: Optional[Mapping[str, Any]] = None,
        operation_id: Optional[str] = None,
        operation_version: Optional[str] = None,
        hash_registry: Optional[HashRegistry] = None,
        cacheable: bool = True,
    ) -> Expression[T]:
        _require_owned_deferred(args, self)
        _require_owned_deferred(kwargs or {}, self)
        return Expression.create(
            operation,
            result=result,
            args=args,
            kwargs=kwargs,
            operation_id=operation_id,
            operation_version=operation_version,
            hash_registry=hash_registry,
            cacheable=cacheable,
        )

    def submit(
        self,
        operation: Callable[..., T],
        *,
        result: ResultSpec[T],
        args: Iterable[Any] = (),
        kwargs: Optional[Mapping[str, Any]] = None,
        operation_id: Optional[str] = None,
        operation_version: Optional[str] = None,
        hash_registry: Optional[HashRegistry] = None,
        cacheable: bool = True,
    ) -> Deferred[T]:
        expression = self.expression(
            operation,
            result=result,
            args=args,
            kwargs=kwargs,
            operation_id=operation_id,
            operation_version=operation_version,
            hash_registry=hash_registry,
            cacheable=cacheable,
        )
        deferred = Deferred(self, expression)
        if self.mode is EvaluationMode.IMMEDIATE:
            self.evaluate(expression)
        return deferred

    def evaluate(self, expression: Union[Expression[T], Deferred[T]]) -> T:
        if isinstance(expression, Deferred):
            if expression.evaluator is not self:
                raise ValueError(
                    "cannot evaluate a Deferred owned by another evaluator"
                )
            expression = expression.expression
        return cast(T, self._evaluate(expression))

    def resolve(self, value: Any) -> Any:
        """Resolve expressions recursively while preserving container types."""

        if isinstance(value, Deferred):
            return self.evaluate(value)
        if isinstance(value, Expression):
            return self._evaluate(value)
        if isinstance(value, list):
            return [self.resolve(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.resolve(item) for item in value)
        if isinstance(value, dict):
            return {
                self.resolve(key): self.resolve(item) for key, item in value.items()
            }
        if isinstance(value, set):
            return {self.resolve(item) for item in value}
        if isinstance(value, frozenset):
            return frozenset(self.resolve(item) for item in value)
        return value

    def clear_memory(self) -> None:
        self._values.clear()

    def operation(
        self,
        function: Optional[Callable[..., T]] = None,
        *,
        result: Optional[Union[ResultSpec[T], Type[T]]] = None,
        operation_id: Optional[str] = None,
        operation_version: Optional[str] = None,
        hash_registry: Optional[HashRegistry] = None,
        cacheable: bool = True,
    ) -> Any:
        """Decorate a function whose calls produce evaluator-bound Deferred values."""

        return _operation_decorator(
            function,
            evaluator=self,
            result=result,
            operation_id=operation_id,
            operation_version=operation_version,
            hash_registry=hash_registry,
            cacheable=cacheable,
        )

    def _evaluate(self, expression: Expression[Any]) -> Any:
        self._emit(EvaluationEventKind.START, expression)
        if expression.digest in self._values:
            self._emit(EvaluationEventKind.MEMORY_HIT, expression)
            value = self._values[expression.digest]
            self._emit(EvaluationEventKind.FINISH, expression)
            return value
        if expression.digest in self._active:
            raise ExpressionError(
                "expression cycle detected at {}".format(expression.operation_id)
            )

        self._active[expression.digest] = expression
        cache_key = self._cache_key(expression)
        try:
            cached = self._read_cache(expression, cache_key)
            if cached is not _MISSING:
                self._values[expression.digest] = cached
                self._emit(
                    EvaluationEventKind.CACHE_HIT,
                    expression,
                    cache_key=cache_key,
                )
                self._emit(EvaluationEventKind.FINISH, expression)
                return cached

            args = tuple(
                self._resolve_argument(argument) for argument in expression.arguments
            )
            kwargs = {
                name: self._resolve_argument(argument)
                for name, argument in expression.keyword_arguments
            }
            value = expression.operation(*args, **kwargs)
            value = expression.result.validate(value, expression.operation_id)
            self._values[expression.digest] = value
            self._write_cache(expression, cache_key, value)
            self._emit(EvaluationEventKind.FINISH, expression)
            return value
        except Exception as error:
            self._emit(
                EvaluationEventKind.ERROR,
                expression,
                cache_key=cache_key,
                detail="{}: {}".format(type(error).__name__, error),
            )
            raise
        finally:
            self._active.pop(expression.digest, None)

    def _resolve_argument(self, argument: _Argument) -> Any:
        if isinstance(argument, Expression):
            return self._evaluate(argument)
        if isinstance(argument, _LiteralArgument):
            return argument.value
        if isinstance(argument, _SequenceArgument):
            values = tuple(self._resolve_argument(item) for item in argument.items)
            if argument.kind == "list":
                return list(values)
            if argument.kind == "tuple":
                return values
            if argument.kind == "set":
                return set(values)
            if argument.kind == "frozenset":
                return frozenset(values)
            raise AssertionError("unknown sequence argument kind")
        if isinstance(argument, _MappingArgument):
            return {
                self._resolve_argument(key): self._resolve_argument(value)
                for key, value in argument.items
            }
        raise AssertionError("unknown argument node")

    def _cache_key(self, expression: Expression[Any]) -> str:
        source = _pack(
            b"evalcache-cache-key-v2",
            self.cache_policy.namespace.encode("utf-8"),
            expression.digest.encode("ascii"),
        )
        return hashlib.sha256(source).hexdigest()

    def _read_cache(
        self,
        expression: Expression[Any],
        cache_key: str,
    ) -> Any:
        if (
            not expression.cacheable
            or not self.cache_policy.read
            or self.cache_store is None
        ):
            return _MISSING
        try:
            record = self.cache_store.get(cache_key)
            if record is None:
                return _MISSING
            if record.schema != 2:
                raise CacheRecordError("unsupported cache record schema")
            if record.result_type_id != expression.result.type_id:
                raise CacheRecordError("cached result type metadata mismatch")
            if record.serializer_id != expression.result.serializer.serializer_id:
                raise CacheRecordError("cached serializer metadata mismatch")
            value = expression.result.serializer.loads(record.value)
            return expression.result.validate(value, expression.operation_id)
        except Exception as error:
            if not self.cache_policy.recover_corrupt:
                raise
            self.cache_store.delete(cache_key)
            self._emit(
                EvaluationEventKind.CACHE_REJECTED,
                expression,
                cache_key=cache_key,
                detail="{}: {}".format(type(error).__name__, error),
            )
            return _MISSING

    def _write_cache(
        self,
        expression: Expression[Any],
        cache_key: str,
        value: Any,
    ) -> None:
        if (
            not expression.cacheable
            or not self.cache_policy.write
            or self.cache_store is None
        ):
            return
        serialized = expression.result.serializer.dumps(value)
        if not isinstance(serialized, SerializedValue):
            raise TypeError("serializer.dumps must return SerializedValue")
        record = CacheRecord(
            schema=2,
            result_type_id=expression.result.type_id,
            serializer_id=expression.result.serializer.serializer_id,
            value=serialized,
        )
        self.cache_store.put(cache_key, record)
        self._emit(
            EvaluationEventKind.CACHE_STORE,
            expression,
            cache_key=cache_key,
        )

    def _emit(
        self,
        kind: EvaluationEventKind,
        expression: Expression[Any],
        *,
        cache_key: Optional[str] = None,
        detail: Optional[str] = None,
    ) -> None:
        if not self.progress_hooks:
            return
        event = EvaluationEvent(
            kind=kind,
            expression_digest=expression.digest,
            operation_id=expression.operation_id,
            cache_key=cache_key,
            detail=detail,
        )
        for hook in self.progress_hooks:
            hook(event)


def _operation_result_spec(
    function: Callable[..., T],
    result: Optional[Union[ResultSpec[T], Type[T]]],
) -> ResultSpec[T]:
    if isinstance(result, ResultSpec):
        return result
    if isinstance(result, type):
        if result is FileArtifact:
            return cast(ResultSpec[T], file_artifact_result())
        return ResultSpec.for_type(result)
    if result is not None:
        raise TypeError("operation result must be a ResultSpec or runtime type")

    try:
        annotation = get_type_hints(function).get(
            "return",
            inspect.Signature.empty,
        )
    except (NameError, TypeError):
        annotation = inspect.signature(function).return_annotation
    if annotation is not inspect.Signature.empty and annotation is not Any:
        if isinstance(annotation, type):
            if annotation is FileArtifact:
                return cast(ResultSpec[T], file_artifact_result())
            return ResultSpec.for_type(annotation)

    type_id = "{}.{}.result".format(
        getattr(function, "__module__", type(function).__module__),
        getattr(function, "__qualname__", type(function).__qualname__),
    )
    return cast(
        ResultSpec[T],
        ResultSpec.for_type(object, type_id=type_id),
    )


class Operation(Generic[T]):
    """A decorated operation definition that creates Deferred calls."""

    def __init__(
        self,
        function: Callable[..., T],
        *,
        result: Optional[Union[ResultSpec[T], Type[T]]] = None,
        evaluator: Optional[Evaluator] = None,
        operation_id: Optional[str] = None,
        operation_version: Optional[str] = None,
        hash_registry: Optional[HashRegistry] = None,
        cacheable: bool = True,
    ) -> None:
        if not callable(function):
            raise TypeError("operation expects a callable")
        self.function = function
        self.result = _operation_result_spec(function, result)
        self.evaluator = evaluator
        self.operation_id = operation_id
        self.operation_version = operation_version
        self.hash_registry = hash_registry
        self.cacheable = cacheable
        functools.update_wrapper(self, function)

    def __call__(self, *args: Any, **kwargs: Any) -> Deferred[T]:
        evaluator = self.evaluator or get_default_evaluator()
        return evaluator.submit(
            self.function,
            result=self.result,
            args=args,
            kwargs=kwargs,
            operation_id=self.operation_id,
            operation_version=self.operation_version,
            hash_registry=self.hash_registry,
            cacheable=self.cacheable,
        )

    def __get__(self, instance: Any, owner: Type[Any]) -> Any:
        if instance is None:
            return self
        return functools.partial(self.__call__, instance)


def _operation_decorator(
    function: Optional[Callable[..., T]],
    *,
    evaluator: Optional[Evaluator],
    result: Optional[Union[ResultSpec[T], Type[T]]],
    operation_id: Optional[str],
    operation_version: Optional[str],
    hash_registry: Optional[HashRegistry],
    cacheable: bool,
) -> Any:
    def decorate(candidate: Callable[..., T]) -> Operation[T]:
        return Operation(
            candidate,
            result=result,
            evaluator=evaluator,
            operation_id=operation_id,
            operation_version=operation_version,
            hash_registry=hash_registry,
            cacheable=cacheable,
        )

    if function is None:
        return decorate
    return decorate(function)


_DEFAULT_EVALUATOR = Evaluator()
_CONFIG_UNSET = object()


def get_default_evaluator() -> Evaluator:
    """Return the process-wide evaluator used by module-level operations."""

    return _DEFAULT_EVALUATOR


def set_default_evaluator(evaluator: Evaluator) -> Evaluator:
    """Replace the process-wide evaluator and return the previous one."""

    if not isinstance(evaluator, Evaluator):
        raise TypeError("default evaluator must be an Evaluator")
    global _DEFAULT_EVALUATOR
    previous = _DEFAULT_EVALUATOR
    _DEFAULT_EVALUATOR = evaluator
    return previous


def configure(
    *,
    mode: Optional[EvaluationMode] = None,
    cache_policy: Optional[CachePolicy] = None,
    cache_store: Any = _CONFIG_UNSET,
    progress_hooks: Optional[Iterable[ProgressHook]] = None,
) -> Evaluator:
    """Replace the default evaluator while retaining unspecified policies."""

    current = get_default_evaluator()
    configured = Evaluator(
        mode=current.mode if mode is None else mode,
        cache_policy=(
            current.cache_policy if cache_policy is None else cache_policy
        ),
        cache_store=(
            current.cache_store if cache_store is _CONFIG_UNSET else cache_store
        ),
        progress_hooks=(
            current.progress_hooks if progress_hooks is None else progress_hooks
        ),
    )
    set_default_evaluator(configured)
    return configured


@contextmanager
def using_evaluator(evaluator: Evaluator) -> Iterator[Evaluator]:
    """Temporarily replace the process-wide evaluator for decorated calls."""

    previous = set_default_evaluator(evaluator)
    try:
        yield evaluator
    finally:
        set_default_evaluator(previous)


def operation(
    function: Optional[Callable[..., T]] = None,
    *,
    result: Optional[Union[ResultSpec[T], Type[T]]] = None,
    operation_id: Optional[str] = None,
    operation_version: Optional[str] = None,
    hash_registry: Optional[HashRegistry] = None,
    cacheable: bool = True,
) -> Any:
    """Decorate a function using the process-wide default evaluator at call time."""

    return _operation_decorator(
        function,
        evaluator=None,
        result=result,
        operation_id=operation_id,
        operation_version=operation_version,
        hash_registry=hash_registry,
        cacheable=cacheable,
    )


def _resolve_legacy_lazy_object(value: Any) -> Any:
    from evalcache.lazy import unlazy

    return unlazy(value)


def legacy_expression(
    value: Any,
    *,
    result: ResultSpec[T],
    hash_registry: Optional[HashRegistry] = None,
) -> Expression[T]:
    """Temporarily adapt a v1 ``LazyObject`` to a typed expression.

    This is a migration bridge, not the extension API for new code.  It keeps
    the legacy graph as one opaque leaf and validates its value on resolution.
    """

    from evalcache.lazy import LazyObject

    if not isinstance(value, LazyObject):
        raise TypeError("legacy_expression expects a LazyObject")
    registry = hash_registry or HashRegistry()
    registry.register(
        LazyObject,
        lambda lazy_value: lazy_value.__lazyhexhash__.encode("ascii"),
        type_id="evalcache.legacy.LazyObject",
    )
    return Expression.create(
        _resolve_legacy_lazy_object,
        result=result,
        args=(value,),
        operation_id="evalcache.legacy.unlazy",
        operation_version="1",
        hash_registry=registry,
        cacheable=False,
    )


__all__ = [
    "Artifact",
    "CachePolicy",
    "CacheRecord",
    "CacheRecordError",
    "CacheStore",
    "Deferred",
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
