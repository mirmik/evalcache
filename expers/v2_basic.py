"""Минимальный пример typed expression API evalcache v2."""

import evalcache


def add(left: int, right: int) -> int:
    print("Выполняется add")
    return left + right


def main() -> None:
    deferred = evalcache.Evaluator(
        mode=evalcache.EvaluationMode.DEFERRED,
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    # Как и оригинальный Lazy, Evaluator можно использовать как декоратор.
    @deferred
    def deferred_add(left: int, right: int) -> int:
        return add(left, right)

    result = deferred_add(20, 22)

    assert isinstance(result, evalcache.Deferred)
    print("Deferred создан, digest:", result.digest)
    print("Результат deferred:", result.compute())
    assert result.unlazy() == 42

    # Immediate вычисляет при вызове, но сохраняет стабильный тип Deferred.
    immediate = evalcache.Evaluator(
        mode=evalcache.EvaluationMode.IMMEDIATE,
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @immediate
    def immediate_add(left: int, right: int) -> int:
        return add(left, right)

    immediate_result = immediate_add(2, 3)
    assert isinstance(immediate_result, evalcache.Deferred)
    print("Результат immediate:", immediate_result.compute())
    assert immediate_result.compute() == 5


if __name__ == "__main__":
    main()
