#!/usr/bin/env python3
"""Export the game's spoiler-light UI background and chapter title cards for web use."""

from __future__ import annotations

import argparse
import importlib.util
import struct
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from build_data import ROUTES, visual_transitions


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSLATION_ROOT = Path("/Users/jw/Desktop/bin/albatross_MTL")


def load_decoder(translation_root: Path):
    path = translation_root / "tools" / "liar_image.py"
    spec = importlib.util.spec_from_file_location("albatross_liar_image", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load image decoder: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def export(translation_root: Path, output_root: Path) -> dict[str, int]:
    decoder = load_decoder(translation_root)
    source = translation_root / "work" / "assets" / "grps"
    title_output = output_root / "chapter-titles"
    title_output.mkdir(parents=True, exist_ok=True)

    background = decoder.decode_wcg_bytes((source / "confback.wcg").read_bytes())
    background.convert("RGB").save(output_root / "confback.webp", "WEBP", quality=84, method=6)

    count = 0
    for path in sorted(source.glob("dt2_*.wcg")):
        slug = path.stem.removeprefix("dt2_")
        image = decoder.decode_wcg_bytes(path.read_bytes())
        image.save(title_output / f"{slug}.webp", "WEBP", lossless=True, method=6)
        count += 1

    referenced: set[int] = set()
    common_final_background = None
    for route in ROUTES:
        current_background = None if route["id"] == "common" else common_final_background
        for slug in route["chapters"]:
            transitions, current_background = visual_transitions(
                translation_root / "work" / "xfl-roundtrip-unpacked" / f"{slug}.gsc",
                current_background,
            )
            referenced.update(transitions.values())
        if route["id"] == "common":
            common_final_background = current_background
    archive = translation_root / "work" / "runtime-original" / "grpe.xfl"
    header = struct.Struct("<4sII")
    entry_struct = struct.Struct("<32sII")
    with archive.open("rb") as handle:
        signature, index_size, entry_count = header.unpack(handle.read(header.size))
        if signature != b"LB\x01\x00" or index_size != entry_count * entry_struct.size:
            raise ValueError(f"Invalid XFL archive: {archive}")
        entries = {}
        for _ in range(entry_count):
            raw_name, offset, size = entry_struct.unpack(handle.read(entry_struct.size))
            name = raw_name.split(b"\0", 1)[0].decode("ascii")
            entries[name] = (offset, size)
        payload_start = header.size + index_size

        background_output = output_root / "backgrounds"
        background_output.mkdir(parents=True, exist_ok=True)
        for image_id in sorted(referenced):
            name = f"{image_id:04d}.wcg"
            if name not in entries:
                raise FileNotFoundError(f"Referenced full-screen image is missing: {name}")
            offset, size = entries[name]
            handle.seek(payload_start + offset)
            image = decoder.decode_wcg_bytes(handle.read(size))
            image.convert("RGB").save(
                background_output / f"{image_id:04d}.webp",
                "WEBP",
                quality=80,
                method=6,
            )
    return {"backgrounds": len(referenced) + 1, "chapter_titles": count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation-root", type=Path, default=DEFAULT_TRANSLATION_ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    counts = export(args.translation_root.resolve(), args.output_root.resolve())
    print(f"exported {counts['backgrounds']} backgrounds and {counts['chapter_titles']} chapter titles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
