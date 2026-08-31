"""Deterministic hashing primitives used by expression identity."""

from __future__ import annotations

import hashlib
import struct
import types
from enum import Enum
from typing import Any, Callable, Dict, Optional, Tuple, Type

from evalcache.errors import HashingError


HashEncoder = Callable[[Any], bytes]


def pack(tag: bytes, *parts: bytes) -> bytes:
    result = bytearray(tag)
    result.extend(b"\x00")
    for part in parts:
        result.extend(len(part).to_bytes(8, "big"))
        result.extend(part)
    return bytes(result)


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
            return pack(b"int", str(value).encode("ascii"))
        if type(value) is float:
            return pack(b"float", struct.pack(">d", value))
        if type(value) is str:
            return pack(b"str", value.encode("utf-8"))
        if type(value) is bytes:
            return pack(b"bytes", value)
        if isinstance(value, Enum):
            enum_type = type(value)
            return pack(
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
                return pack(b"custom", type_id.encode("utf-8"), payload)

        hook = getattr(value, "__evalcache_key__", None)
        if hook is not None:
            if not callable(hook):
                raise HashingError("__evalcache_key__ must be callable")
            payload = hook()
            if not isinstance(payload, bytes):
                raise HashingError("__evalcache_key__ must return bytes")
            value_type = type(value)
            return pack(
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


def _code_constant_bytes(value: Any, registry: HashRegistry) -> bytes:
    if isinstance(value, types.CodeType):
        return _code_bytes(value, registry)
    if isinstance(value, tuple):
        return pack(
            b"constant-tuple",
            *(_code_constant_bytes(item, registry) for item in value),
        )
    if isinstance(value, frozenset):
        items = sorted(_code_constant_bytes(item, registry) for item in value)
        return pack(b"constant-frozenset", *items)
    return registry.encode(value)


def _code_bytes(code: types.CodeType, registry: HashRegistry) -> bytes:
    return pack(
        b"python-code-v1",
        code.co_code,
        pack(
            b"constants",
            *(_code_constant_bytes(constant, registry) for constant in code.co_consts),
        ),
        pack(b"names", *(name.encode("utf-8") for name in code.co_names)),
        pack(b"varnames", *(name.encode("utf-8") for name in code.co_varnames)),
        pack(b"freevars", *(name.encode("utf-8") for name in code.co_freevars)),
        str(code.co_argcount).encode("ascii"),
        str(code.co_kwonlyargcount).encode("ascii"),
    )


def callable_identity(
    operation: Callable[..., Any],
    registry: HashRegistry,
) -> Tuple[str, str]:
    module = getattr(operation, "__module__", type(operation).__module__)
    qualname = getattr(operation, "__qualname__", type(operation).__qualname__)
    operation_id = module + "." + qualname
    code = getattr(operation, "__code__", None)
    if code is None:
        version_source = pack(b"callable-name", operation_id.encode("utf-8"))
    else:
        parts = [_code_bytes(code, registry)]
        defaults = getattr(operation, "__defaults__", None) or ()
        parts.append(
            pack(
                b"defaults",
                *(_code_constant_bytes(value, registry) for value in defaults),
            )
        )
        keyword_defaults = getattr(operation, "__kwdefaults__", None) or {}
        parts.append(
            pack(
                b"keyword-defaults",
                *(
                    pack(
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
            pack(
                b"closure",
                *(
                    _code_constant_bytes(cell.cell_contents, registry)
                    for cell in closure
                ),
            )
        )
        version_source = pack(b"python-callable-v1", *parts)
    return operation_id, hashlib.sha256(version_source).hexdigest()
