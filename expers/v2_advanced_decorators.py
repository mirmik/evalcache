"""Расширенные параметры декораторов evalcache v2."""

import json
from dataclasses import dataclass

import evalcache


@dataclass(frozen=True)
class Job:
    name: str
    complexity: int


def encode_job(job: Job) -> bytes:
    """Стабильное представление доменного аргумента для digest."""

    return json.dumps(
        {"complexity": job.complexity, "name": job.name},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def main() -> None:
    events = []
    store = evalcache.MemoryCacheStore()
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy(namespace="advanced-example"),
        cache_store=store,
        progress_hooks=(events.append,),
    )

    hashes = evalcache.HashRegistry()
    hashes.register(Job, encode_job, type_id="examples.job.v1")

    score_result = evalcache.ResultSpec.for_type(
        int,
        type_id="examples.non-negative-score.v1",
        validator=lambda value: value >= 0,
    )

    # operation_id обозначает логическую операцию, а не имя Python-функции.
    # Версию повышают, когда старая запись кэша больше не является корректной.
    @evaluator.operation(
        operation_id="examples.calculate-job-score",
        operation_version="1",
        result=score_result,
        hash_registry=hashes,
    )
    def calculate_score_v1(job: Job) -> int:
        return job.complexity * 10

    @evaluator.operation(
        operation_id="examples.calculate-job-score",
        operation_version="2",
        result=score_result,
        hash_registry=hashes,
    )
    def calculate_score_v2(job: Job) -> int:
        return job.complexity * 10 + len(job.name)

    job = Job("render", 4)
    old = calculate_score_v1(job)
    current = calculate_score_v2(job)

    assert old.operation_id == current.operation_id
    assert old.digest != current.digest
    assert old.compute() == 40
    assert current.compute() == 46

    # После очистки памяти результат v2 восстанавливается из CacheStore.
    evaluator.clear_memory()
    assert calculate_score_v2(job).compute() == 46
    assert any(event.kind.value == "cache_hit" for event in events)

    live_calls = 0

    @evaluator.operation(
        operation_id="examples.read-live-job-status",
        operation_version="1",
        result=str,
        hash_registry=hashes,
        cacheable=False,
    )
    def read_live_status(job: Job) -> str:
        nonlocal live_calls
        live_calls += 1
        return "{}:ready".format(job.name)

    assert read_live_status(job).compute() == "render:ready"
    evaluator.clear_memory()
    assert read_live_status(job).compute() == "render:ready"
    assert live_calls == 2

    print("operation_id:", calculate_score_v2.operation_id)
    print("operation_version:", calculate_score_v2.operation_version)
    print("digest v1:", old.digest)
    print("digest v2:", current.digest)
    print("Некэшируемая операция выполнена раз:", live_calls)


if __name__ == "__main__":
    main()
