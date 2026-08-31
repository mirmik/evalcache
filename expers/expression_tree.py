"""Дерево зависимых выражений и повторное использование узлов."""

import evalcache


calls = {"multiply": 0}


def main() -> None:
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator
    def multiply(left: int, right: int) -> int:
        calls["multiply"] += 1
        return left * right

    @evaluator
    def describe(values: list[int]) -> str:
        return " + ".join(str(value) for value in values)

    product = multiply(6, 7)
    total = product + product
    message = describe([product, total])

    # product встречается в графе несколько раз, но в памяти Evaluator
    # вычисляется только однажды.
    assert message.compute() == "42 + 84"
    assert calls == {"multiply": 1}
    print("Результат:", message.compute())
    print("Число вызовов:", calls)

    # resolve удобен, когда Expression находится внутри обычного контейнера.
    resolved = evaluator.resolve({"product": product, "items": [total, product]})
    assert resolved == {"product": 42, "items": [84, 42]}
    print("Разрешённый контейнер:", resolved)


if __name__ == "__main__":
    main()
