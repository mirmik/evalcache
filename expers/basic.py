"""Минимальный пример декораторного API evalcache."""

import evalcache


def main() -> None:
    previous = evalcache.get_default_evaluator()
    calls = 0
    try:
        evalcache.configure(cache_policy=evalcache.CachePolicy.disabled())

        @evalcache.operation
        def add(left: int, right: int) -> int:
            nonlocal calls
            calls += 1
            return left + right

        result = add(20, 22)
        assert isinstance(result, evalcache.Deferred)
        assert calls == 0
        assert result.compute() == 42
        assert calls == 1

        print("Deferred создан, digest:", result.digest)
        print("Результат:", result.compute())
    finally:
        evalcache.set_default_evaluator(previous)


if __name__ == "__main__":
    main()
