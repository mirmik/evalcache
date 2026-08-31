import evalcache
import pytest


@evalcache.operation(
    operation_id="tests.default-add",
    operation_version="1",
)
def default_add(left: int, right: int) -> int:
    return left + right


def test_evaluator_decorator_infers_result_and_returns_deferred():
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator
    def add(left: int, right: int) -> int:
        return left + right

    result = add(20, 22)

    assert isinstance(add, evalcache.Operation)
    assert add.result.expected_type is int
    assert isinstance(result, evalcache.Deferred)
    assert isinstance(result.expression, evalcache.Expression)
    assert result.compute() == 42
    assert result.evaluate() == 42
    assert result.unlazy() == 42
    assert evalcache.unlazy(result) == 42
    assert evalcache.unlazy_if_need(result) == 42


def test_decorated_calls_form_a_graph_and_preserve_containers():
    calls = {"multiply": 0, "add": 0, "describe": 0}
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator.operation(
        operation_id="tests.decorated-multiply",
        operation_version="1",
    )
    def multiply(left: int, right: int) -> int:
        calls["multiply"] += 1
        return left * right

    @evaluator.operation(
        operation_id="tests.decorated-add",
        operation_version="1",
    )
    def add(left: int, right: int) -> int:
        calls["add"] += 1
        return left + right

    @evaluator.operation(
        operation_id="tests.decorated-describe",
        operation_version="1",
    )
    def describe(values: dict) -> str:
        calls["describe"] += 1
        return "{} + {}".format(values["product"], values["total"])

    product = multiply(6, 7)
    total = add(product, product)
    message = describe({"product": product, "total": total})

    assert message.compute() == "42 + 84"
    assert calls == {"multiply": 1, "add": 1, "describe": 1}
    assert evaluator.resolve([product, (total,)]) == [42, (84,)]


def test_immediate_decorator_evaluates_now_but_still_returns_deferred():
    calls = []
    evaluator = evalcache.Evaluator(
        mode=evalcache.EvaluationMode.IMMEDIATE,
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator.operation(
        operation_id="tests.immediate-square",
        operation_version="1",
    )
    def square(value: int) -> int:
        calls.append(value)
        return value * value

    result = square(12)

    assert isinstance(result, evalcache.Deferred)
    assert calls == [12]
    assert result.compute() == 144
    assert calls == [12]


def test_unannotated_operation_accepts_dynamic_results():
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator.operation(
        operation_id="tests.dynamic-result",
        operation_version="1",
    )
    def make_result(value):
        return {"value": value}

    assert make_result.result.expected_type is object
    assert make_result(42).compute() == {"value": 42}


def test_module_decorator_uses_default_evaluator_at_call_time():
    first = evalcache.Evaluator(cache_policy=evalcache.CachePolicy.disabled())
    second = evalcache.Evaluator(cache_policy=evalcache.CachePolicy.disabled())

    with evalcache.using_evaluator(first):
        first_result = default_add(20, 22)
    with evalcache.using_evaluator(second):
        second_result = default_add(2, 3)

    assert first_result.evaluator is first
    assert second_result.evaluator is second
    assert first_result.compute() == 42
    assert second_result.compute() == 5


def test_configure_replaces_default_policies_without_redecorating():
    previous = evalcache.get_default_evaluator()
    store = evalcache.MemoryCacheStore()
    try:
        configured = evalcache.configure(
            mode=evalcache.EvaluationMode.IMMEDIATE,
            cache_store=store,
        )
        result = default_add(40, 2)

        assert result.evaluator is configured
        assert configured.mode is evalcache.EvaluationMode.IMMEDIATE
        assert result.compute() == 42
        assert store.records
    finally:
        evalcache.set_default_evaluator(previous)


def test_deferred_values_from_different_evaluators_cannot_mix():
    first = evalcache.Evaluator(cache_policy=evalcache.CachePolicy.disabled())
    second = evalcache.Evaluator(cache_policy=evalcache.CachePolicy.disabled())

    @first.operation
    def source(value: int) -> int:
        return value

    @second.operation
    def consume(value: int) -> int:
        return value

    with pytest.raises(ValueError, match="different evaluators"):
        consume(source(42))
