"""Immutable file results that can be materialized outside the cache."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Union

from evalcache.cache import (
    Artifact,
    ResultSpec,
    SerializedValue,
    validate_artifact_fields,
)
from evalcache.hashing import pack


@dataclass(frozen=True)
class FileArtifact:
    """Immutable file contents, independent from a materialization path."""

    name: str
    data: bytes
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        validate_artifact_fields(self.name, self.data, self.media_type)

    @classmethod
    def from_path(
        cls,
        path: Union[str, os.PathLike[str]],
        *,
        name: Optional[str] = None,
        media_type: str = "application/octet-stream",
    ) -> "FileArtifact":
        source = Path(path).expanduser()
        return cls(
            name=source.name if name is None else name,
            data=source.read_bytes(),
            media_type=media_type,
        )

    @property
    def content_digest(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    def __evalcache_key__(self) -> bytes:
        return pack(
            b"file-artifact-v1",
            self.name.encode("utf-8"),
            self.media_type.encode("utf-8"),
            bytes.fromhex(self.content_digest),
        )

    def materialize(self, path: Union[str, os.PathLike[str]]) -> Path:
        """Atomically write this artifact to an explicit destination path."""

        destination = Path(path).expanduser()
        parent = destination.parent
        if not parent.is_dir():
            raise FileNotFoundError(
                "artifact destination directory does not exist: {}".format(parent)
            )
        if destination.is_dir():
            raise IsADirectoryError(str(destination))

        descriptor, temporary_path = tempfile.mkstemp(
            prefix=".{}-".format(destination.name),
            suffix=".tmp",
            dir=str(parent),
        )
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(self.data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, str(destination))
        finally:
            try:
                os.remove(temporary_path)
            except FileNotFoundError:
                pass
        return destination


_FILE_ARTIFACT_PAYLOAD = b"evalcache.file-artifact\x00v1"


class FileArtifactSerializer:
    serializer_id = "evalcache.file-artifact.v1"

    def dumps(self, value: FileArtifact) -> SerializedValue:
        if not isinstance(value, FileArtifact):
            raise TypeError("file artifact serializer requires FileArtifact")
        return SerializedValue(
            payload=_FILE_ARTIFACT_PAYLOAD,
            artifacts=(Artifact(value.name, value.data, value.media_type),),
        )

    def loads(self, value: SerializedValue) -> FileArtifact:
        if value.payload != _FILE_ARTIFACT_PAYLOAD:
            raise ValueError("unsupported file artifact cache payload")
        if len(value.artifacts) != 1:
            raise ValueError("file artifact cache record must contain one artifact")
        artifact = value.artifacts[0]
        return FileArtifact(artifact.name, artifact.data, artifact.media_type)


_FILE_ARTIFACT_SERIALIZER = FileArtifactSerializer()


def file_artifact_result(
    *,
    type_id: str = "evalcache.FileArtifact.v1",
    validator: Optional[Callable[[FileArtifact], bool]] = None,
) -> ResultSpec[FileArtifact]:
    return ResultSpec.for_type(
        FileArtifact,
        type_id=type_id,
        serializer=_FILE_ARTIFACT_SERIALIZER,
        validator=validator,
    )
