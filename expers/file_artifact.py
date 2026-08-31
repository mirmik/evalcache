"""Кэшируемое содержимое файла и явная материализация по пути."""

from pathlib import Path
from tempfile import TemporaryDirectory

import evalcache


def main() -> None:
    calls = 0
    events = []
    evaluator = evalcache.Evaluator(
        cache_store=evalcache.MemoryCacheStore(),
        progress_hooks=(events.append,),
    )

    @evaluator.operation(
        operation_id="examples.render-report",
        operation_version="1",
        result=evalcache.file_artifact_result(
            type_id="examples.text-report.v1",
        ),
    )
    def render_report(title: str, value: int) -> evalcache.FileArtifact:
        nonlocal calls
        calls += 1
        contents = "{}\nresult={}\n".format(title, value).encode("utf-8")
        return evalcache.FileArtifact(
            name="report.txt",
            data=contents,
            media_type="text/plain",
        )

    report = render_report("Experiment", 42)

    with TemporaryDirectory() as directory:
        root = Path(directory)

        # Путь назначения не является аргументом операции и не входит в digest.
        first_path = report.materialize(root / "first-report.txt")

        # Имитируем новый запуск: память пуста, но CacheStore сохранён.
        evaluator.clear_memory()
        same_report = render_report("Experiment", 42)
        second_path = same_report.materialize(root / "second-report.txt")

        assert first_path.read_bytes() == second_path.read_bytes()
        assert report.digest == same_report.digest
        assert calls == 1
        assert any(event.kind.value == "cache_hit" for event in events)

        print("Первый путь:", first_path)
        print("Второй путь:", second_path)
        print("SHA-256 содержимого:", same_report.compute().content_digest)
        print("Функция выполнена раз:", calls)


if __name__ == "__main__":
    main()
