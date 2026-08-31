import json
import struct
import subprocess
import sys
from dataclasses import dataclass

import pytest

import evalcache
from evalcache.dircache_v2 import DirCache_v2


def add(left, right):
    return left + right


def wrong_result():
    return "not an integer"


def container_contract(values):
    return (
        type(values["list"]) is list,
        type(values["tuple"]) is tuple,
        type(values["set"]) is set,
        values["list"][0] == values["tuple"][0],
    )


@dataclass(frozen=True)
class ExternalValue:
    x: int
    y: int


class ExternalValueSerializer:
    serializer_id = "tests.external-value.v1"

    def dumps(self, value):
        payload = json.dumps([value.x, value.y]).encode("utf-8")
        artifact = evalcache.Artifact(
            name="coordinates.json",
            data=payload,
            media_type="application/json",
        )
        return evalcache.SerializedValue(payload, (artifact,))

    def loads(self, serialized):
        assert serialized.artifacts[0].name == "coordinates.json"
        x, y = json.loads(serialized.payload.decode("utf-8"))
        return ExternalValue(x, y)


def translate_external(value, dx, dy):
    return ExternalValue(value.x + dx, value.y + dy)


class SpyStore(evalcache.MemoryCacheStore):
    def __init__(self):
        super().__init__()
        self.get_count = 0
        self.put_count = 0
        self.delete_count = 0

    def get(self, key):
        self.get_count += 1
        return super().get(key)

    def put(self, key, record):
        self.put_count += 1
        super().put(key, record)

    def delete(self, key):
        self.delete_count += 1
        super().delete(key)


def int_expression(*args, **kwargs):
    return evalcache.Expression.create(
        add,
        result=evalcache.ResultSpec.for_type(int),
        args=args,
        operation_id="tests.add",
        operation_version="1",
        **kwargs,
    )


def test_expression_identity_is_deterministic_and_typed():
    first = int_expression(2, 3)
    same = int_expression(2, 3)
    different_argument = int_expression(2, 4)
    different_result = evalcache.Expression.create(
        add,
        result=evalcache.ResultSpec.for_type(
            int,
            type_id="tests.other-int-contract",
        ),
        args=(2, 3),
        operation_id="tests.add",
        operation_version="1",
    )

    assert first.digest == same.digest
    assert first.digest != different_argument.digest
    assert first.digest != different_result.digest
    assert len(first.digest) == 64


def test_immediate_and_deferred_modes_share_expression_semantics():
    spec = evalcache.ResultSpec.for_type(int)
    deferred = evalcache.Evaluator(mode=evalcache.EvaluationMode.DEFERRED)
    immediate = evalcache.Evaluator(mode=evalcache.EvaluationMode.IMMEDIATE)

    deferred_result = deferred.submit(
        add,
        result=spec,
        args=(20, 22),
        operation_id="tests.add",
        operation_version="1",
    )
    immediate_result = immediate.submit(
        add,
        result=spec,
        args=(20, 22),
        operation_id="tests.add",
        operation_version="1",
    )

    assert isinstance(deferred_result, evalcache.Deferred)
    assert isinstance(immediate_result, evalcache.Deferred)
    assert deferred.evaluate(deferred_result) == 42
    assert immediate_result.compute() == 42


def test_nested_graph_and_container_resolution_preserve_types():
    child = int_expression(20, 22)
    expression = evalcache.Expression.create(
        container_contract,
        result=evalcache.ResultSpec.for_type(tuple),
        args=(
            {
                "list": [child],
                "tuple": (child,),
                "set": {child},
            },
        ),
        operation_id="tests.container-contract",
        operation_version="1",
    )
    evaluator = evalcache.Evaluator()

    assert evaluator.evaluate(expression) == (True, True, True, True)
    assert evaluator.resolve([child, (child,)]) == [42, (42,)]


def test_cache_policy_can_disable_all_store_access():
    store = SpyStore()
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
        cache_store=store,
    )

    assert evaluator.evaluate(int_expression(2, 3)) == 5
    assert (store.get_count, store.put_count, store.delete_count) == (0, 0, 0)


def test_persistent_cache_round_trip_and_progress_events():
    calls = []
    events = []

    def counted_add(left, right):
        calls.append((left, right))
        return left + right

    expression = evalcache.Expression.create(
        counted_add,
        result=evalcache.ResultSpec.for_type(int),
        args=(20, 22),
        operation_id="tests.counted-add",
        operation_version="1",
    )
    store = evalcache.MemoryCacheStore()
    first = evalcache.Evaluator(
        cache_store=store,
        progress_hooks=(events.append,),
    )
    second = evalcache.Evaluator(
        cache_store=store,
        progress_hooks=(events.append,),
    )

    assert first.evaluate(expression) == 42
    assert second.evaluate(expression) == 42
    assert calls == [(20, 22)]
    kinds = [event.kind for event in events]
    assert evalcache.EvaluationEventKind.CACHE_STORE in kinds
    assert evalcache.EvaluationEventKind.CACHE_HIT in kinds


def test_mapping_store_adapts_dircache_v2(tmp_path):
    first_mapping = DirCache_v2(str(tmp_path / "cache"))
    first_store = evalcache.MappingCacheStore(first_mapping)
    expression = int_expression(20, 22)

    assert evalcache.Evaluator(cache_store=first_store).evaluate(expression) == 42

    second_mapping = DirCache_v2(str(tmp_path / "cache"))
    second_store = evalcache.MappingCacheStore(second_mapping)
    evaluator = evalcache.Evaluator(cache_store=second_store)
    assert evaluator.evaluate(expression) == 42


def test_result_type_mismatch_is_reported_at_evaluator_boundary():
    expression = evalcache.Expression.create(
        wrong_result,
        result=evalcache.ResultSpec.for_type(int),
        operation_id="tests.wrong-result",
        operation_version="1",
    )

    with pytest.raises(
        evalcache.ResultTypeError,
        match="declared builtins.int but produced builtins.str",
    ):
        evalcache.Evaluator().evaluate(expression)


def test_corrupt_cache_record_is_removed_and_recomputed():
    store = evalcache.MemoryCacheStore()
    events = []
    expression = int_expression(20, 22)
    first = evalcache.Evaluator(cache_store=store)
    assert first.evaluate(expression) == 42
    cache_key = next(iter(store.records))
    store.records[cache_key] = evalcache.CacheRecord(
        schema=1,
        result_type_id="wrong",
        serializer_id="wrong",
        value=evalcache.SerializedValue(b"wrong"),
    )

    second = evalcache.Evaluator(
        cache_store=store,
        progress_hooks=(events.append,),
    )
    assert second.evaluate(expression) == 42
    assert any(
        event.kind is evalcache.EvaluationEventKind.CACHE_REJECTED for event in events
    )


def test_external_domain_type_uses_registered_hash_and_artifact_serializer():
    registry = evalcache.HashRegistry()
    registry.register(
        ExternalValue,
        lambda value: struct.pack(">qq", value.x, value.y),
        type_id="tests.ExternalValue",
    )
    spec = evalcache.ResultSpec.for_type(
        ExternalValue,
        type_id="tests.ExternalValue",
        serializer=ExternalValueSerializer(),
    )
    expression = evalcache.Expression.create(
        translate_external,
        result=spec,
        args=(ExternalValue(1, 2), 10, 20),
        operation_id="tests.translate-external",
        operation_version="1",
        hash_registry=registry,
    )
    store = evalcache.MemoryCacheStore()

    assert evalcache.Evaluator(cache_store=store).evaluate(expression) == ExternalValue(
        11,
        22,
    )
    record = next(iter(store.records.values()))
    assert record.value.artifacts[0].name == "coordinates.json"
    assert evalcache.Evaluator(cache_store=store).evaluate(expression) == ExternalValue(
        11,
        22,
    )


def test_legacy_lazy_object_adapter_is_an_explicit_opaque_leaf():
    lazy = evalcache.Lazy(cache={}, encache=False, decache=False)

    @lazy
    def old_add(left, right):
        return left + right

    expression = evalcache.legacy_expression(
        old_add(20, 22),
        result=evalcache.ResultSpec.for_type(int),
    )

    assert expression.cacheable is False
    assert expression.operation_id == "evalcache.legacy.unlazy"
    assert evalcache.Evaluator().evaluate(expression) == 42


def test_explicit_operation_identity_is_stable_across_fresh_processes():
    code = """
import operator
import evalcache
expression = evalcache.Expression.create(
    operator.add,
    result=evalcache.ResultSpec.for_type(int),
    args=(20, 22),
    operation_id='tests.operator-add',
    operation_version='1',
)
print(expression.digest)
"""

    first = subprocess.check_output([sys.executable, "-c", code], text=True)
    second = subprocess.check_output([sys.executable, "-c", code], text=True)
    assert first.strip() == second.strip()
