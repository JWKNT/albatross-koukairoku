#!/usr/bin/env python3
"""Maintainer utility: generate redistributable deltas from verified builds."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from delta_codec import create_delta, sha256


FILES = {
    "english-scr": "scr.xfl",
    "english-grps": "grps.xfl",
    "english-grpo": "grpo.xfl",
    "english-grpe": "grpe.xfl",
    "english-grpo-ex": "grpo_ex.xfl",
    "macos-fullscreen-exe": "信天翁航海録.exe",
}


def create_or_reuse_delta(source: Path, target: Path, destination: Path) -> dict:
    manifest = destination / "manifest.json"
    if manifest.is_file():
        existing = json.loads(manifest.read_text(encoding="utf-8"))
        if (
            existing.get("source_size") == source.stat().st_size
            and existing.get("target_size") == target.stat().st_size
            and existing.get("source_sha256") == sha256(source)
            and existing.get("target_sha256") == sha256(target)
        ):
            return existing
    if destination.exists():
        shutil.rmtree(destination)
    return create_delta(source, target, destination)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("japanese", type=Path)
    parser.add_argument("current", type=Path)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name("payload")
    )
    args = parser.parse_args()
    japanese = args.japanese.resolve()
    current = args.current.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    report = {}
    for patch_name, filename in FILES.items():
        source = japanese / filename
        target = current / filename
        if not source.is_file() or not target.is_file():
            raise FileNotFoundError(f"missing delta endpoint for {filename}")
        print(f"Building {patch_name}...")
        report[patch_name] = create_or_reuse_delta(
            source, target, output / patch_name
        )
    summary = {
        "format": "albatross-complete-patcher-payload-v1",
        "files": report,
    }
    (output / "build-report.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
