"""Постоянный кэш v2 поверх существующего файлового DirCache_v2."""

import sys
from pathlib import Path

import evalcache


calls = 0


@evalcache.operation(
    operation_id="examples.expensive-square",
    operation_version="1",
    result=int,
)
def expensive_square(value: int) -> int:
    global calls
    calls += 1
    print("Выполняется дорогое вычисление")
    return value * value


def main(cache_dir: str = ".evalcache-v2-example") -> None:
    mapping = evalcache.DirCache_v2(cache_dir)
    store = evalcache.MappingCacheStore(mapping)
    events = []

    first = evalcache.Evaluator(
        cache_store=store,
        progress_hooks=(events.append,),
    )
    with evalcache.using_evaluator(first):
        assert expensive_square(12).compute() == 144

    # Новый Evaluator не имеет результатов в памяти, поэтому читает с диска.
    second = evalcache.Evaluator(
        cache_store=store,
        progress_hooks=(events.append,),
    )
    with evalcache.using_evaluator(second):
        assert expensive_square(12).compute() == 144

    event_names = [event.kind.value for event in events]
    assert "cache_hit" in event_names
    print("Каталог кэша:", Path(cache_dir).resolve())
    print("Функция выполнена в этом процессе раз:", calls)
    print("События:", event_names)


if __name__ == "__main__":
    directory = sys.argv[1] if len(sys.argv) > 1 else ".evalcache-v2-example"
    main(directory)
