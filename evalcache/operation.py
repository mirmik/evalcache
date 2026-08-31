"""Decorator-first API and process-wide evaluator configuration."""

from __future__ import annotations

import functools
import inspect
from contextlib import contextmanager
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
    get_origin,
    get_type_hints,
)

from evalcache.artifacts import FileArtifact, file_artifact_result
from evalcache.cache import CachePolicy, ResultSpec
from evalcache.evaluation import (
    EvaluationMode,
    Evaluator,
    ProgressHook,
)
from evalcache.expression import Deferred, Expression
from evalcache.hashing import HashRegistry


T = TypeVar("T")


def _runtime_result_type(annotation: Any) -> Optional[Type[Any]]:
    """Return the runtime-checkable type represented by an annotation."""

    origin = get_origin(annotation)
    if isinstance(origin, type):
        return origin
    if isinstance(annotation, type):
        return annotation
    return None


def _operation_result_spec(
    function: Callable[..., T],
    result: Optional[Union[ResultSpec[T], Type[T]]],
) -> ResultSpec[T]:
    if isinstance(result, ResultSpec):
        return result
    runtime_result_type = _runtime_result_type(result)
    if runtime_result_type is not None:
        if runtime_result_type is FileArtifact:
            return cast(ResultSpec[T], file_artifact_result())
        return cast(ResultSpec[T], ResultSpec.for_type(runtime_result_type))
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
        runtime_result_type = _runtime_result_type(annotation)
        if runtime_result_type is not None:
            if runtime_result_type is FileArtifact:
                return cast(ResultSpec[T], file_artifact_result())
            return cast(ResultSpec[T], ResultSpec.for_type(runtime_result_type))

    type_id = "{}.{}.result".format(
        getattr(function, "__module__", type(function).__module__),
        getattr(function, "__qualname__", type(function).__qualname__),
    )
    return cast(ResultSpec[T], ResultSpec.for_type(object, type_id=type_id))


class Operation(Generic[T]):
    """A decorated operation definition whose calls return Deferred values."""

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
        cache_policy=current.cache_policy if cache_policy is None else cache_policy,
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
    """Decorate a function using the default evaluator at call time."""

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
    """Treat a legacy LazyObject graph as one opaque expression leaf."""

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
