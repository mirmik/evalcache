"""Immutable expression graphs and evaluator-bound deferred results."""

from __future__ import annotations

import hashlib
import operator
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Mapping,
    Optional,
    Tuple,
    TYPE_CHECKING,
    TypeVar,
    Union,
)

from evalcache.artifacts import FileArtifact
from evalcache.cache import ResultSpec
from evalcache.hashing import HashRegistry, callable_identity, pack


T = TypeVar("T")

if TYPE_CHECKING:
    from evalcache.evaluation import Evaluator


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
        return pack(b"expression", argument.digest.encode("ascii"))
    if isinstance(argument, _LiteralArgument):
        return pack(b"literal", argument.encoded)
    if isinstance(argument, _SequenceArgument):
        return pack(
            b"sequence",
            argument.kind.encode("ascii"),
            *(_argument_bytes(item) for item in argument.items),
        )
    if isinstance(argument, _MappingArgument):
        return pack(
            b"mapping",
            *(
                pack(b"item", _argument_bytes(key), _argument_bytes(value))
                for key, value in argument.items
            ),
        )
    raise AssertionError("unknown argument node")


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
            default_id, default_version = callable_identity(operation, registry)
            resolved_id = operation_id or default_id
            resolved_version = operation_version or default_version
        if not resolved_id or not resolved_version:
            raise ValueError("operation identity and version must not be empty")

        frozen_args = tuple(_freeze_argument(value, registry) for value in args)
        frozen_kwargs = tuple(
            (name, _freeze_argument(value, registry))
            for name, value in (kwargs or {}).items()
        )
        digest_source = pack(
            b"evalcache-expression-v1",
            resolved_id.encode("utf-8"),
            resolved_version.encode("utf-8"),
            result.type_id.encode("utf-8"),
            result.serializer.serializer_id.encode("utf-8"),
            b"cacheable:1" if cacheable else b"cacheable:0",
            pack(b"args", *(_argument_bytes(arg) for arg in frozen_args)),
            pack(
                b"kwargs",
                *(
                    pack(
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

    def materialize(self, path: Union[str, os.PathLike[str]]) -> Path:
        """Compute and materialize a FileArtifact result."""

        value = self.compute()
        if not isinstance(value, FileArtifact):
            raise TypeError("Deferred.materialize requires a FileArtifact result")
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
        return self._reflected_operator(other, "matrix_multiply", operator.matmul)

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


def deferred_values(value: Any) -> Iterable[Deferred[Any]]:
    if isinstance(value, Deferred):
        yield value
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from deferred_values(key)
            yield from deferred_values(item)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from deferred_values(item)


def require_owned_deferred(value: Any, evaluator: Any) -> None:
    for deferred in deferred_values(value):
        if deferred.evaluator is not evaluator:
            raise ValueError("cannot mix Deferred values from different evaluators")
