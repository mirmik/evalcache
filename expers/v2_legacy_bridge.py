"""Временный мост от старого LazyObject к typed Expression v2."""

import evalcache


def main() -> None:
    legacy = evalcache.Lazy(cache={}, encache=False, decache=False)

    @legacy
    def old_add(left: int, right: int) -> int:
        return left + right

    old_lazy_object = old_add(20, 22)
    expression = evalcache.legacy_expression(
        old_lazy_object,
        result=evalcache.ResultSpec.for_type(int),
    )

    # Всё старое дерево вычисляется старым unlazy как один непрозрачный узел.
    # Новые выражения могут использовать результат этого узла как зависимость.
    evaluator = evalcache.Evaluator()

    @evaluator
    def double(value: int) -> int:
        return value * 2

    result = double(expression).compute()
    assert result == 84
    assert expression.cacheable is False
    print("Результат старого графа внутри v2:", result)


if __name__ == "__main__":
    main()
