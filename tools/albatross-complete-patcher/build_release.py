#!/usr/bin/env python3
"""Create a deterministic, self-contained patcher release archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


PATCHER = Path(__file__).resolve().parent
EXCLUDED = {"build_deltas.py", "build_release.py"}
FIXED_TIME = (2026, 8, 14, 0, 0, 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def included_files() -> list[Path]:
    files = []
    for path in PATCHER.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.name in EXCLUDED or path.suffix == ".pyc":
            continue
        files.append(path)
    return sorted(files, key=lambda path: path.relative_to(PATCHER).as_posix())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload_report = PATCHER / "payload/build-report.json"
    if not payload_report.is_file():
        raise FileNotFoundError("build the verified payload before packaging")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    prefix = "albatross-complete-patcher"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in included_files():
            relative = path.relative_to(PATCHER).as_posix()
            info = zipfile.ZipInfo(f"{prefix}/{relative}", FIXED_TIME)
            mode = 0o755 if path.suffix == ".command" else 0o644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    result = {
        "format": "albatross-patcher-release-v1",
        "version": args.version,
        "archive": str(output),
        "bytes": output.stat().st_size,
        "sha256": sha256(output),
        "files": len(included_files()),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
