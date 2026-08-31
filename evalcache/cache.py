"""Cache policies, serialization contracts, and storage backends."""

from __future__ import annotations

import os
import pickle
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    MutableMapping,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
    runtime_checkable,
)

from evalcache.errors import CacheRecordError, ResultTypeError


T = TypeVar("T")


@dataclass(frozen=True)
class CachePolicy:
    """Persistent cache policy; in-memory DAG reuse is always enabled."""

    read: bool = True
    write: bool = True
    namespace: str = "evalcache"
    recover_corrupt: bool = True

    def __post_init__(self) -> None:
        if not self.namespace:
            raise ValueError("cache namespace must not be empty")

    @classmethod
    def disabled(cls, namespace: str = "evalcache") -> "CachePolicy":
        return cls(read=False, write=False, namespace=namespace)

    @property
    def enabled(self) -> bool:
        return self.read or self.write


@dataclass(frozen=True)
class Artifact:
    """A named binary attachment emitted by a result serializer."""

    name: str
    data: bytes
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        validate_artifact_fields(self.name, self.data, self.media_type)


def validate_artifact_fields(name: str, data: bytes, media_type: str) -> None:
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
    """Default serializer for cache directories trusted by the current user."""

    serializer_id = "python.pickle.v5"

    def dumps(self, value: T) -> SerializedValue:
        return SerializedValue(pickle.dumps(value, protocol=5))

    def loads(self, value: SerializedValue) -> T:
        return cast(T, pickle.loads(value.payload))


_DEFAULT_SERIALIZER: PickleSerializer[Any] = PickleSerializer()
ExpectedType = Union[Type[Any], Tuple[Type[Any], ...]]


@dataclass(frozen=True)
class ResultSpec(Generic[T]):
    """Runtime type metadata and serialization contract for a result."""

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


class DirectoryCacheStore:
    """Store cache records as atomically replaced files in a directory."""

    def __init__(self, path: Union[str, os.PathLike[str]]) -> None:
        self.path = Path(path).expanduser()
        self.path.mkdir(parents=True, exist_ok=True)
        self._temporary_path = self.path / "tmp"
        self._temporary_path.mkdir(exist_ok=True)

    def get(self, key: str) -> Optional[CacheRecord]:
        path = self._record_path(key)
        try:
            with path.open("rb") as stream:
                record = pickle.load(stream)
        except FileNotFoundError:
            return None
        if not isinstance(record, CacheRecord):
            raise CacheRecordError(
                "cache key {} does not contain an evalcache record".format(key)
            )
        return record

    def put(self, key: str, record: CacheRecord) -> None:
        if not isinstance(record, CacheRecord):
            raise TypeError("DirectoryCacheStore accepts CacheRecord values")
        path = self._record_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(dir=str(self._temporary_path))
        try:
            with os.fdopen(descriptor, "wb") as stream:
                pickle.dump(record, stream, protocol=5)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, str(path))
        finally:
            try:
                os.remove(temporary_name)
            except FileNotFoundError:
                pass

    def delete(self, key: str) -> None:
        try:
            self._record_path(key).unlink()
        except FileNotFoundError:
            pass

    def clear(self) -> None:
        for prefix in self.path.iterdir():
            if (
                prefix == self._temporary_path
                or not prefix.is_dir()
                or len(prefix.name) != 2
                or any(
                    character not in "0123456789abcdef"
                    for character in prefix.name
                )
            ):
                continue
            for record in prefix.iterdir():
                if (
                    record.is_file()
                    and len(record.name) == 62
                    and all(
                        character in "0123456789abcdef"
                        for character in record.name
                    )
                ):
                    record.unlink()
            try:
                prefix.rmdir()
            except OSError:
                pass

    def _record_path(self, key: str) -> Path:
        if (
            not isinstance(key, str)
            or len(key) != 64
            or any(character not in "0123456789abcdef" for character in key)
        ):
            raise ValueError("cache key must be a lowercase SHA-256 digest")
        return self.path / key[:2] / key[2:]


class MappingCacheStore:
    """Adapt an existing mutable mapping to the CacheStore protocol."""

    def __init__(self, mapping: MutableMapping[str, Any]) -> None:
        self.mapping = mapping

    def get(self, key: str) -> Optional[CacheRecord]:
        if key not in self.mapping:
            return None
        record = self.mapping[key]
        if not isinstance(record, CacheRecord):
            raise CacheRecordError(
                "cache key {} does not contain an evalcache record".format(key)
            )
        return record

    def put(self, key: str, record: CacheRecord) -> None:
        self.mapping[key] = record

    def delete(self, key: str) -> None:
        try:
            del self.mapping[key]
        except KeyError:
            pass
