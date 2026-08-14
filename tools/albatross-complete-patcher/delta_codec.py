#!/usr/bin/env python3
"""Dependency-free, content-defined binary delta codec.

Patch payloads contain only target bytes absent from a verified source file.
Unchanged ranges are copied from the user's Japanese installation. Literal
data is zlib-compressed and split below GitHub's per-object size limit.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import zlib
from pathlib import Path
from typing import BinaryIO, Iterator


FORMAT = "albatross-delta-v1"
MIN_CHUNK = 8 * 1024
AVERAGE_CHUNK = 32 * 1024
MAX_CHUNK = 128 * 1024
PART_LIMIT = 45 * 1024 * 1024
MASK = AVERAGE_CHUNK - 1
GEAR = tuple(
    int.from_bytes(hashlib.sha256(bytes([value])).digest()[:8], "little")
    for value in range(256)
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def chunks(path: Path) -> Iterator[tuple[int, bytes]]:
    """Yield deterministic content-defined chunks without loading the file."""
    offset = 0
    pending = bytearray()
    rolling = 0
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            for value in block:
                pending.append(value)
                rolling = ((rolling << 1) + GEAR[value]) & 0xFFFFFFFFFFFFFFFF
                size = len(pending)
                if size >= MIN_CHUNK and ((rolling & MASK) == 0 or size >= MAX_CHUNK):
                    yield offset, bytes(pending)
                    offset += size
                    pending.clear()
                    rolling = 0
    if pending:
        yield offset, bytes(pending)


def _fingerprint(data: bytes) -> bytes:
    return hashlib.blake2s(data, digest_size=16).digest()


def create_delta(source: Path, target: Path, output: Path) -> dict[str, object]:
    source = source.resolve()
    target = target.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source_index: dict[bytes, list[tuple[int, int]]] = {}
    for offset, data in chunks(source):
        source_index.setdefault(_fingerprint(data), []).append((offset, len(data)))

    operations: list[list[int | str]] = []
    literal_bytes = 0
    copied_bytes = 0
    with tempfile.NamedTemporaryFile(prefix="albatross-literals-", delete=False) as literals:
        literal_path = Path(literals.name)
        try:
            with source.open("rb") as source_stream:
                for _, data in chunks(target):
                    match = None
                    for candidate_offset, candidate_size in source_index.get(
                        _fingerprint(data), []
                    ):
                        if candidate_size != len(data):
                            continue
                        source_stream.seek(candidate_offset)
                        if source_stream.read(candidate_size) == data:
                            match = (candidate_offset, candidate_size)
                            break
                    if match is not None:
                        candidate_offset, candidate_size = match
                        if operations and operations[-1][0] == "copy":
                            previous = operations[-1]
                            if int(previous[1]) + int(previous[2]) == candidate_offset:
                                previous[2] = int(previous[2]) + candidate_size
                            else:
                                operations.append(["copy", candidate_offset, candidate_size])
                        else:
                            operations.append(["copy", candidate_offset, candidate_size])
                        copied_bytes += candidate_size
                    else:
                        if operations and operations[-1][0] == "literal":
                            operations[-1][1] = int(operations[-1][1]) + len(data)
                        else:
                            operations.append(["literal", len(data)])
                        literals.write(data)
                        literal_bytes += len(data)

            parts: list[dict[str, object]] = []
            compressor = zlib.compressobj(level=9)
            part_number = 1
            part_stream: BinaryIO | None = None
            part_path: Path | None = None
            part_hash = hashlib.sha256()
            part_size = 0

            def close_part() -> None:
                nonlocal part_stream, part_path, part_hash, part_size
                if part_stream is None or part_path is None:
                    return
                part_stream.close()
                parts.append(
                    {
                        "name": part_path.name,
                        "size": part_size,
                        "sha256": part_hash.hexdigest(),
                    }
                )
                part_stream = None

            def write_compressed(data: bytes) -> None:
                nonlocal part_stream, part_path, part_hash, part_size, part_number
                view = memoryview(data)
                while view:
                    if part_stream is None:
                        part_path = output / f"literals.zlib.{part_number:03d}"
                        part_stream = part_path.open("wb")
                        part_hash = hashlib.sha256()
                        part_size = 0
                        part_number += 1
                    take = min(len(view), PART_LIMIT - part_size)
                    piece = view[:take]
                    part_stream.write(piece)
                    part_hash.update(piece)
                    part_size += take
                    view = view[take:]
                    if part_size == PART_LIMIT:
                        close_part()

            with literal_path.open("rb") as raw:
                while block := raw.read(4 * 1024 * 1024):
                    write_compressed(compressor.compress(block))
            write_compressed(compressor.flush())
            close_part()
        finally:
            literal_path.unlink(missing_ok=True)

    manifest = {
        "format": FORMAT,
        "source_size": source.stat().st_size,
        "source_sha256": sha256(source),
        "target_size": target.stat().st_size,
        "target_sha256": sha256(target),
        "operations": operations,
        "literal_bytes": literal_bytes,
        "copied_bytes": copied_bytes,
        "parts": parts,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


class LiteralReader:
    def __init__(self, root: Path, parts: list[dict[str, object]]) -> None:
        self._root = root
        self._parts = iter(parts)
        self._current: BinaryIO | None = None
        self._decompressor = zlib.decompressobj()
        self._buffer = bytearray()
        self._finished = False

    def _compressed_block(self) -> bytes:
        while True:
            if self._current is not None:
                block = self._current.read(1024 * 1024)
                if block:
                    return block
                self._current.close()
                self._current = None
            try:
                part = next(self._parts)
            except StopIteration:
                return b""
            path = self._root / str(part["name"])
            if path.stat().st_size != int(part["size"]) or sha256(path) != part["sha256"]:
                raise ValueError(f"Corrupt patch payload: {path.name}")
            self._current = path.open("rb")

    def read_exact(self, size: int) -> bytes:
        while len(self._buffer) < size and not self._finished:
            block = self._compressed_block()
            if block:
                self._buffer.extend(self._decompressor.decompress(block))
            else:
                self._buffer.extend(self._decompressor.flush())
                self._finished = True
        if len(self._buffer) < size:
            raise EOFError("Patch literal stream ended early")
        result = bytes(self._buffer[:size])
        del self._buffer[:size]
        return result

    def close(self) -> None:
        if self._current is not None:
            self._current.close()
            self._current = None


def apply_delta(source: Path, patch: Path, output: Path) -> dict[str, object]:
    manifest = json.loads((patch / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != FORMAT:
        raise ValueError(f"Unsupported delta format in {patch}")
    if (
        source.stat().st_size != manifest["source_size"]
        or sha256(source) != manifest["source_sha256"]
    ):
        raise ValueError(
            f"Source file does not match the supported Japanese release: {source}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    literals = LiteralReader(patch, manifest["parts"])
    try:
        with source.open("rb") as original, output.open("wb") as rebuilt:
            for operation in manifest["operations"]:
                if operation[0] == "copy":
                    original.seek(int(operation[1]))
                    remaining = int(operation[2])
                    while remaining:
                        block = original.read(min(4 * 1024 * 1024, remaining))
                        if not block:
                            raise EOFError("Source file ended during copy operation")
                        rebuilt.write(block)
                        remaining -= len(block)
                elif operation[0] == "literal":
                    rebuilt.write(literals.read_exact(int(operation[1])))
                else:
                    raise ValueError(f"Unknown delta operation: {operation[0]}")
    finally:
        literals.close()

    if (
        output.stat().st_size != manifest["target_size"]
        or sha256(output) != manifest["target_sha256"]
    ):
        output.unlink(missing_ok=True)
        raise ValueError(f"Rebuilt file failed verification: {output}")
    return manifest
