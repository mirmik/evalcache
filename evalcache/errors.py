"""Exceptions shared by evalcache's expression and cache layers."""


class ExpressionError(Exception):
    """Base exception for expression construction and evaluation."""


class HashingError(ExpressionError, TypeError):
    """A value cannot participate in deterministic expression identity."""


class ResultTypeError(ExpressionError, TypeError):
    """An operation produced a value outside its declared result contract."""


class CacheRecordError(ExpressionError):
    """A persistent cache record is invalid or incompatible."""
