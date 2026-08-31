from dataclasses import dataclass

import evalcache
import pytest


@dataclass(frozen=True)
class Matrix:
    value: int

    def __evalcache_key__(self):
        return str(self.value).encode("ascii")

    def __matmul__(self, other):
        if not isinstance(other, Matrix):
            return NotImplemented
        return Matrix(self.value * other.value)


def value_operation(evaluator):
    @evaluator
    def value(item: object) -> object:
        return item

    return value


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (lambda value: +value, 6),
        (lambda value: -value, -6),
        (lambda value: abs(value), 6),
        (lambda value: ~value, -7),
        (lambda value: value + 4, 10),
        (lambda value: value - 4, 2),
        (lambda value: value * 4, 24),
        (lambda value: value / 4, 1.5),
        (lambda value: value // 4, 1),
        (lambda value: value % 4, 2),
        (lambda value: value**2, 36),
        (lambda value: value & 3, 2),
        (lambda value: value | 3, 7),
        (lambda value: value ^ 3, 5),
        (lambda value: value << 2, 24),
        (lambda value: value >> 1, 3),
    ],
)
def test_unary_and_binary_operators_build_deferred_nodes(build, expected):
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )
    value = value_operation(evaluator)(6)

    result = build(value)

    assert isinstance(result, evalcache.Deferred)
    assert result.compute() == expected


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (lambda value: 4 + value, 10),
        (lambda value: 10 - value, 4),
        (lambda value: 4 * value, 24),
        (lambda value: 24 / value, 4),
        (lambda value: 25 // value, 4),
        (lambda value: 14 % value, 2),
        (lambda value: 2**value, 64),
        (lambda value: 3 & value, 2),
        (lambda value: 3 | value, 7),
        (lambda value: 3 ^ value, 5),
        (lambda value: 3 << value, 192),
        (lambda value: 96 >> value, 1),
    ],
)
def test_reflected_operators_preserve_operand_order(build, expected):
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )
    value = value_operation(evaluator)(6)

    assert build(value).compute() == expected


def test_matrix_multiplication_and_reflected_matrix_multiplication():
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator
    def matrix(value: int) -> Matrix:
        return Matrix(value)

    right = matrix(6)

    assert (right @ Matrix(7)).compute() == Matrix(42)
    assert (Matrix(7) @ right).compute() == Matrix(42)


def test_getitem_keeps_container_evaluation_deferred():
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator
    def load_values() -> list:
        return [10, 20, 30]

    selected = load_values()[1]

    assert isinstance(selected, evalcache.Deferred)
    assert selected.operation_id == "evalcache.operator.getitem"
    assert selected.compute() == 20


def test_operator_graph_reuses_equal_upstream_expressions():
    calls = []
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator.operation(
        operation_id="tests.operator-source",
        operation_version="1",
    )
    def source(value: int) -> int:
        calls.append(value)
        return value

    result = (source(10) + source(10)) * 2

    assert result.compute() == 40
    assert calls == [10]
    assert result.operation_id == "evalcache.operator.multiply"


def test_operator_nodes_follow_immediate_policy_but_remain_deferred():
    evaluator = evalcache.Evaluator(
        mode=evalcache.EvaluationMode.IMMEDIATE,
        cache_policy=evalcache.CachePolicy.disabled(),
    )
    value = value_operation(evaluator)(6)

    result = value * 7

    assert isinstance(result, evalcache.Deferred)
    assert result.compute() == 42


def test_deferred_has_no_implicit_truth_value():
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )
    value = value_operation(evaluator)(1)

    with pytest.raises(TypeError, match="no implicit truth value"):
        bool(value)


def test_deferred_is_not_implicitly_iterable():
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled()
    )

    @evaluator
    def values() -> tuple[int, ...]:
        return (1, 2, 3)

    with pytest.raises(TypeError, match="not implicitly iterable"):
        iter(values())


@pytest.mark.parametrize(
    "compare",
    [
        lambda value: value == 1,
        lambda value: value != 1,
        lambda value: value < 1,
        lambda value: value <= 1,
        lambda value: value > 1,
        lambda value: value >= 1,
    ],
)
def test_deferred_comparisons_are_explicit_boundaries(compare):
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled()
    )
    value = value_operation(evaluator)(1)

    with pytest.raises(TypeError, match="comparisons are not supported"):
        compare(value)
