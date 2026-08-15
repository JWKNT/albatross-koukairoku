#!/usr/bin/env python3
"""Export the game's reader art, irreversibly censoring audited adult CGs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageFilter

sys.dont_write_bytecode = True

from build_data import ROUTES, visual_transitions


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSLATION_ROOT = Path("/Users/jw/Desktop/local-work/albatross_MTL")

# Conservative full-screen-art audit: explicit nudity or sexual activity,
# sexualized bed scenes/exposure, and implied sexual assault. Keeping this list
# in the exporter prevents a future asset rebuild from republishing originals.
NSFW_IMAGE_RANGES = (
    (21, 22),
    (41, 43),
    (71, 75),
    (81, 87),
    (121, 125),
    (131, 133),
    (141, 145),
    (151, 160),
    (201, 206),
    (252, 257),
    (261, 266),
    (271, 273),
    (281, 286),
    (311, 317),
    (401, 407),
    (411, 423),
    (431, 436),
    (441, 454),
    (551, 553),
    (561, 566),
    (571, 578),
    (581, 587),
    (681, 683),
)
NSFW_IMAGE_IDS = frozenset(
    image_id
    for first, last in NSFW_IMAGE_RANGES
    for image_id in range(first, last + 1)
)
MOSAIC_SIZE = (12, 9)
BLUR_RADIUS = 6


def censor_image(image: Image.Image) -> Image.Image:
    """Make an entire CG unreadable with large mosaic blocks and blur."""
    original = image.convert("RGB")
    mosaic = original.resize(MOSAIC_SIZE, Image.Resampling.BOX).resize(
        original.size,
        Image.Resampling.NEAREST,
    )
    return mosaic.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))


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
        censored: list[str] = []
        for image_id in sorted(referenced):
            name = f"{image_id:04d}.wcg"
            if name not in entries:
                raise FileNotFoundError(f"Referenced full-screen image is missing: {name}")
            offset, size = entries[name]
            handle.seek(payload_start + offset)
            image = decoder.decode_wcg_bytes(handle.read(size))
            output_image = image.convert("RGB")
            if image_id in NSFW_IMAGE_IDS:
                output_image = censor_image(image)
                censored.append(f"{image_id:04d}.webp")
            output_image.save(
                background_output / f"{image_id:04d}.webp",
                "WEBP",
                quality=80,
                method=6,
            )
        manifest = {
            "count": len(censored),
            "criteria": (
                "Explicit nudity or sexual activity, sexualized bed scenes/exposure, "
                "and implied sexual assault."
            ),
            "method": (
                f"Full-frame {MOSAIC_SIZE[0]}x{MOSAIC_SIZE[1]} mosaic, "
                f"nearest-neighbor upscale, Gaussian blur radius {BLUR_RADIUS}."
            ),
            "images": censored,
        }
        (background_output / "censored-images.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
    return {
        "backgrounds": len(referenced) + 1,
        "censored": len(censored),
        "chapter_titles": count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation-root", type=Path, default=DEFAULT_TRANSLATION_ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / "assets")
    args = parser.parse_args()
    counts = export(args.translation_root.resolve(), args.output_root.resolve())
    print(
        f"exported {counts['backgrounds']} backgrounds "
        f"({counts['censored']} censored) and {counts['chapter_titles']} chapter titles"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
