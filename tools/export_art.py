#!/usr/bin/env python3
"""Export the game's spoiler-light UI background and chapter title cards for web use."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


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
    return {"backgrounds": 1, "chapter_titles": count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation-root", type=Path, default=DEFAULT_TRANSLATION_ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    counts = export(args.translation_root.resolve(), args.output_root.resolve())
    print(f"exported {counts['backgrounds']} background and {counts['chapter_titles']} chapter titles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
