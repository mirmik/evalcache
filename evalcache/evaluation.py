"""Expression evaluation, cache policy enforcement, and progress events."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    Mapping,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)

from evalcache.cache import (
    CachePolicy,
    CacheRecord,
    CacheRecordError,
    CacheStore,
    ResultSpec,
    SerializedValue,
)
from evalcache.errors import ExpressionError
from evalcache.expression import (
    Deferred,
    Expression,
    _Argument,
    _LiteralArgument,
    _MappingArgument,
    _SequenceArgument,
    require_owned_deferred,
)
from evalcache.hashing import HashRegistry, pack


T = TypeVar("T")


class EvaluationMode(str, Enum):
    DEFERRED = "deferred"
    IMMEDIATE = "immediate"


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
    """Resolve expressions according to evaluation and cache policy."""

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
        require_owned_deferred(args, self)
        require_owned_deferred(kwargs or {}, self)
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
                raise ValueError("cannot evaluate a Deferred owned by another evaluator")
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

        from evalcache.operation import _operation_decorator

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
        source = pack(
            b"evalcache-cache-key-v1",
            self.cache_policy.namespace.encode("utf-8"),
            expression.digest.encode("ascii"),
        )
        return hashlib.sha256(source).hexdigest()

    def _read_cache(self, expression: Expression[Any], cache_key: str) -> Any:
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
            if record.schema != 1:
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
            schema=1,
            result_type_id=expression.result.type_id,
            serializer_id=expression.result.serializer.serializer_id,
            value=serialized,
        )
        self.cache_store.put(cache_key, record)
        self._emit(EvaluationEventKind.CACHE_STORE, expression, cache_key=cache_key)

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
