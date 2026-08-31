import hashlib

import evalcache
import pytest


def test_file_artifact_snapshots_and_atomically_materializes(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"first contents")
    artifact = evalcache.FileArtifact.from_path(
        source,
        name="result.bin",
        media_type="application/x-example",
    )

    source.write_bytes(b"changed source")
    destination = tmp_path / "destination.bin"
    destination.write_bytes(b"old destination")

    materialized = artifact.materialize(destination)

    assert materialized == destination
    assert destination.read_bytes() == b"first contents"
    assert artifact.name == "result.bin"
    assert artifact.media_type == "application/x-example"
    assert artifact.content_digest == hashlib.sha256(b"first contents").hexdigest()
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "destination.bin",
        "source.bin",
    ]


@pytest.mark.parametrize("name", ["", ".", "..", "nested/file", "nested\\file"])
def test_file_artifact_name_must_be_a_basename(name):
    with pytest.raises(ValueError, match="basename"):
        evalcache.FileArtifact(name, b"contents")


def test_file_artifact_requires_an_existing_destination_directory(tmp_path):
    artifact = evalcache.FileArtifact("result.bin", b"contents")

    with pytest.raises(FileNotFoundError, match="directory does not exist"):
        artifact.materialize(tmp_path / "missing" / "result.bin")


def test_decorated_file_artifact_round_trips_through_cache(tmp_path):
    calls = []
    events = []
    store = evalcache.MemoryCacheStore()
    evaluator = evalcache.Evaluator(
        cache_store=store,
        progress_hooks=(events.append,),
    )

    @evaluator.operation(
        operation_id="tests.render-file-artifact",
        operation_version="1",
    )
    def render(value: int) -> evalcache.FileArtifact:
        calls.append(value)
        return evalcache.FileArtifact(
            name="answer.txt",
            data="answer={}\n".format(value).encode("utf-8"),
            media_type="text/plain",
        )

    first = render(42)
    first_path = first.materialize(tmp_path / "first.txt")
    evaluator.clear_memory()
    second = render(42)
    second_path = second.materialize(tmp_path / "second.txt")

    assert first.digest == second.digest
    assert first_path.read_bytes() == b"answer=42\n"
    assert second_path.read_bytes() == b"answer=42\n"
    assert calls == [42]
    assert render.result.expected_type is evalcache.FileArtifact
    assert render.result.serializer.serializer_id == "evalcache.file-artifact.v1"
    assert any(
        event.kind is evalcache.EvaluationEventKind.CACHE_HIT for event in events
    )

    record = next(iter(store.records.values()))
    assert record.value.payload == b"evalcache.file-artifact\x00v1"
    assert record.value.artifacts == (
        evalcache.Artifact(
            name="answer.txt",
            data=b"answer=42\n",
            media_type="text/plain",
        ),
    )


def test_explicit_file_artifact_result_contract_is_available():
    result = evalcache.file_artifact_result(type_id="tests.report-file.v1")
    artifact = evalcache.FileArtifact("report.txt", b"report")

    serialized = result.serializer.dumps(artifact)

    assert result.type_id == "tests.report-file.v1"
    assert result.validate(
        result.serializer.loads(serialized),
        "tests.report",
    ) == artifact


def test_file_artifact_round_trips_through_directory_cache(tmp_path):
    calls = []

    def render(value):
        calls.append(value)
        return evalcache.FileArtifact("result.bin", bytes([value]))

    expression = evalcache.Expression.create(
        render,
        result=evalcache.file_artifact_result(),
        args=(42,),
        operation_id="tests.directory-file-artifact",
        operation_version="1",
    )
    cache_directory = tmp_path / "cache"
    first_store = evalcache.DirectoryCacheStore(cache_directory)
    second_store = evalcache.DirectoryCacheStore(cache_directory)

    first = evalcache.Evaluator(cache_store=first_store).evaluate(expression)
    second = evalcache.Evaluator(cache_store=second_store).evaluate(expression)

    assert first == second == evalcache.FileArtifact("result.bin", b"*")
    assert calls == [42]


def test_file_artifact_has_deterministic_expression_identity():
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator
    def artifact_size(artifact: evalcache.FileArtifact) -> int:
        return len(artifact.data)

    first = artifact_size(evalcache.FileArtifact("one.bin", b"contents"))
    same = artifact_size(evalcache.FileArtifact("one.bin", b"contents"))
    renamed = artifact_size(evalcache.FileArtifact("two.bin", b"contents"))

    assert first.digest == same.digest
    assert first.digest != renamed.digest
    assert first.compute() == 8


def test_non_artifact_deferred_cannot_be_materialized(tmp_path):
    evaluator = evalcache.Evaluator(
        cache_policy=evalcache.CachePolicy.disabled(),
    )

    @evaluator
    def answer() -> int:
        return 42

    with pytest.raises(TypeError, match="requires a FileArtifact"):
        answer().materialize(tmp_path / "answer.txt")
