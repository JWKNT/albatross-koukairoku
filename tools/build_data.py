#!/usr/bin/env python3
"""Build compact route-aware reader data from the Albatross MTL workspace."""

from __future__ import annotations

import argparse
import csv
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRANSLATION_ROOT = Path("/Users/jw/Desktop/bin/albatross_MTL")

ROUTES = [
    {
        "id": "common",
        "label": "Common Voyage",
        "shortLabel": "Common",
        "description": "The shared opening voyage aboard the Albatross.",
        "chapters": [f"10{index:02d}" for index in range(1, 22)],
    },
    {
        "id": "kuro",
        "label": "Kuro Voyage",
        "shortLabel": "Kuro",
        "description": "Kuro's parallel character voyage, with two endings.",
        "chapters": [f"20{index:02d}" for index in range(1, 16)],
        "fork": {
            "at": "2013",
            "choices": [
                {"chapter": "2014", "label": "Do not release her"},
                {"chapter": "2015", "label": "Release her"},
            ],
        },
    },
    {
        "id": "twins",
        "label": "Sisam & Kisara Voyage",
        "shortLabel": "Sisam & Kisara",
        "description": "The twins' parallel character voyage, with two endings.",
        "chapters": [f"30{index:02d}" for index in range(1, 19)],
        "fork": {
            "at": "3016",
            "choices": [
                {"chapter": "3017", "label": "Cry out"},
                {"chapter": "3018", "label": "Drag them away"},
            ],
        },
    },
    {
        "id": "rui",
        "label": "Rui Voyage",
        "shortLabel": "Rui",
        "description": "Rui's parallel character voyage, with two endings.",
        "chapters": [f"40{index:02d}" for index in range(1, 20)],
        "fork": {
            "at": "4017",
            "choices": [
                {"chapter": "4018", "label": "Think of something"},
                {"chapter": "4019", "label": "Think of nothing"},
            ],
        },
    },
    {
        "id": "final",
        "label": "Final Voyage",
        "shortLabel": "Final",
        "description": "The concluding story, after the three character voyages.",
        "chapters": [f"50{index:02d}" for index in range(1, 12)],
        "unlockNote": "Read after the Kuro, Sisam & Kisara, and Rui voyages.",
    },
]

SPEAKERS = {
    "直正": "Naomasa",
    "泪": "Rui",
    "彩久津泪": "Rui Irokuzu",
    "クロ": "Kuro",
    "キサラ": "Kisara",
    "シサム": "Sisam",
    "密航者": "Stowaway",
    "水夫長": "Boatswain",
    "下級水夫": "Deckhand",
    "智里": "Tomosato",
    "酒場のお姉さん": "Barmaid",
    "機関長": "Chief Engineer",
    "声": "Voice",
    "ノア": "Noah",
    "禿頭の水夫": "Bald Sailor",
    "巡礼者": "Pilgrim",
    "金持ち": "Rich Man",
    "鬼島": "Kijima",
    "魚怪": "Fish Creature",
    "老人": "Old Man",
    "老人の声": "Old Man's Voice",
    "青年": "Young Man",
    "下級水夫達": "Deckhands",
    "塩辛入道": "Shiokara Nyudo",
    "父王": "King",
    "店主": "Proprietor",
    "酒場の船乗り": "Tavern Sailor",
    "金髪の美女・右": "Blonde Woman (Right)",
    "金髪の美女・左": "Blonde Woman (Left)",
    "恐ろしい顔の男": "Frightening Man",
    "金髪の双子": "Blonde Twins",
    "？？？": "???",
    "手下": "Henchman",
    "バーテンダー": "Bartender",
    "和服の男": "Man in Japanese Dress",
    "和装の男": "Man in Japanese Dress",
    "女客": "Woman",
    "娘": "Girl",
    "漁船からの声": "Voice from the Fishing Boat",
    "影": "Shadow",
    "アルビノの女の子": "Albino Girl",
    "前の凶漢": "Thug in Front",
    "漂流者": "Castaway",
    "背後の凶漢": "Thug Behind",
    "伝声管からの声": "Voice from the Speaking Tube",
    "少女": "Girl",
    "禿頭の船乗り": "Bald Sailor",
    "もう一人の金髪の女": "Other Blonde Woman",
    "下級水夫その一": "First Deckhand",
    "下級水夫その二": "Second Deckhand",
    "下級水夫その三": "Third Deckhand",
    "下級水夫その四": "Fourth Deckhand",
    "信天翁号の下級水夫": "Albatross Deckhand",
    "双子の女": "Twin Woman",
    "宗右衛門": "Soemon",
    "時雨宗右衛門": "Soemon Shigure",
    "男の子": "Boy",
    "白スーツの金持ち": "Rich Man in a White Suit",
    "短艇の下級水夫": "Launch Deckhand",
    "老呪術師": "Old Sorcerer",
    "金髪の女": "Blonde Woman",
    "伝声管からの機関長の声": "Chief Engineer over the Speaking Tube",
    "凶漢": "Thug",
    "小太りの男": "Stocky Man",
    "智正": "Tomomasa",
    "親役の下級水夫": "Parent-role Deckhand",
    "酒場の客": "Tavern Patron",
    "長身の男": "Tall Man",
    "露店店主": "Stallkeeper",
}

CONTROL_RE = re.compile(r"\[\[(?:NL|CTRL)_\d+\]\]")

# Operand counts for the game's low VM opcode family. Each regular operand is
# a four-byte value. The few sentinel values below describe the handful of
# fixed-width instructions whose layouts differ.
VM_OPERANDS = {
    0x03: 1, 0x04: 1, 0x05: 1, 0x08: 0, 0x09: "u16", 0x0A: 0, 0x0B: 0,
    0x0C: 2, 0x0D: 1, 0x0E: "choice", 0x0F: "call", 0x10: 1, 0x11: 0,
    0x12: 2, 0x13: 1, 0x14: 2, 0x15: 1, 0x16: 4, 0x17: 4, 0x18: 2,
    0x19: 2, 0x1A: 0, 0x1B: 0, 0x1C: 3, 0x1D: 2, 0x1E: 6,
    0x20: 6, 0x21: 5, 0x22: 5, 0x23: 2, 0x24: 2, 0x25: 2,
    0x26: 4, 0x27: 3, 0x28: 2, 0x29: 2, 0x2A: 2, 0x2B: 2,
    0x2C: 1, 0x2D: 2, 0x2E: 1, 0x2F: 2, 0x30: 3, 0x31: 2,
    0x32: 0, 0x33: 0, 0x34: 0, 0x35: 1, 0x37: 0, 0x38: 5,
    0x39: 0, 0x3A: 0, 0x3B: 4, 0x3C: 3, 0x3D: 2, 0x3E: 1,
    0x3F: 3, 0x40: 1, 0x41: 1, 0x42: 4, 0x43: 1, 0x44: 0,
    0x45: 0, 0x46: 4, 0x47: 4, 0x48: 1, 0x49: 3, 0x4A: 1,
    0x4B: 5, 0x4D: 4, 0x50: 1, 0x51: 7, 0x52: 6, 0x53: 1,
    0x5A: 3, 0x5B: 5, 0x5C: 2, 0x5D: 2, 0x5E: 1, 0x5F: 2,
    0x60: 2, 0x61: 2, 0x62: 2, 0x63: 3, 0x64: 3, 0x65: 2,
    0x66: 1, 0x67: 2, 0x68: 4, 0x69: 2, 0x6E: 3, 0x6F: 3,
    0x70: 1, 0x71: 2, 0x72: 2, 0x73: 2, 0x74: 2, 0x75: 2,
    0x78: 2, 0x79: 2, 0x82: 4, 0x83: 5, 0x84: 2, 0x86: 3,
    0x87: 5, 0x88: 3, 0x96: 2, 0x97: 2, 0x98: 2, 0x99: 2,
    0x9A: 2, 0x9B: 2, 0x9C: 3, 0x9D: 5, 0x9E: 2, 0x9F: 2,
    0xC8: "return", 0xC9: 5, 0xCA: 3, 0xD2: 2, 0xD3: 4, 0xD4: 1,
    0xD5: 3, 0xDC: 3, 0xDD: 2, 0xDE: 0, 0xDF: 2, 0xE1: 5,
    0xE6: 1, 0xE7: 1, 0xFF: 5,
}

GSC_HEADER = struct.Struct("<9I")


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def normalize_text(value: str) -> str:
    return CONTROL_RE.sub("\n", value or "").replace("\r\n", "\n").strip()


def parse_vm(code: bytes):
    """Yield aligned VM instructions as (offset, opcode, operands)."""
    cursor = 0
    while cursor < len(code):
        offset = cursor
        opcode = struct.unpack_from("<H", code, cursor)[0]
        cursor += 2
        operands: list[int] = []
        family = opcode & 0xF000
        if family:
            cursor += 4 if family == 0xF000 else 6
        else:
            layout = VM_OPERANDS.get(opcode)
            if layout is None:
                raise ValueError(f"Unknown GSC opcode 0x{opcode:04X} at 0x{offset:X}")
            if layout == "u16":
                cursor += 2
            elif layout == "choice":
                count = struct.unpack_from("<H", code, cursor)[0] & 0xFF
                operands = [
                    struct.unpack_from("<I", code, cursor + 26 + index * 4)[0]
                    for index in range(count)
                ]
                cursor += 58
            elif layout == "call":
                cursor += 48
            elif layout == "return":
                cursor += 44
            else:
                operands = [
                    struct.unpack_from("<I", code, cursor + index * 4)[0]
                    for index in range(layout)
                ]
                cursor += layout * 4
        if cursor > len(code):
            raise ValueError(f"GSC instruction at 0x{offset:X} overruns the code region")
        yield offset, opcode, operands


def visual_transitions(
    gsc_path: Path, initial_background: int | None = None
) -> tuple[dict[int, int], int | None]:
    """Map text-pool indices to full-screen changes and return the final state."""
    data = gsc_path.read_bytes()
    if len(data) < GSC_HEADER.size:
        raise ValueError(f"Truncated GSC: {gsc_path}")
    header = GSC_HEADER.unpack_from(data)
    code_size, text_index_size, text_pool_size = header[2:5]
    code = data[GSC_HEADER.size : GSC_HEADER.size + code_size]
    text_index_start = GSC_HEADER.size + code_size
    text_pool_start = text_index_start + text_index_size
    offsets = [
        struct.unpack_from("<I", data, text_index_start + offset)[0]
        for offset in range(0, text_index_size, 4)
    ]
    localizable_indices: list[int] = []
    for index, offset in enumerate(offsets):
        start = text_pool_start + offset
        end = data.index(0, start, text_pool_start + text_pool_size)
        value = data[start:end].decode("cp932")
        if value and not value.startswith(("grpo", "REP")):
            localizable_indices.append(index)

    current_background = initial_background
    pending_background: int | None = initial_background
    by_text_index: dict[int, int] = {}
    for _, opcode, operands in parse_vm(code):
        if opcode == 0x14:
            current_background = operands[0]
            pending_background = current_background
            continue
        if opcode == 0x51:
            text_index = operands[5]
        elif opcode == 0x52:
            text_index = operands[4]
        elif opcode == 0x0E and operands:
            text_index = operands[0]
        else:
            continue
        if pending_background is not None and text_index in localizable_indices:
            by_text_index[text_index] = pending_background
            pending_background = None

    return (
        {
            position: by_text_index[text_index]
            for position, text_index in enumerate(localizable_indices, start=1)
            if text_index in by_text_index
        },
        current_background,
    )


def batch_directory(root: Path, slug: str) -> Path:
    batches = root / "project" / "batches"
    special = {
        "1001": batches / "pilot-001_1001",
        "1002": batches / "batch-002_1002",
    }
    return special.get(slug, batches / f"chapter-{slug}")


def route_for(slug: str) -> dict[str, object]:
    for route in ROUTES:
        if slug in route["chapters"]:
            return route
    raise KeyError(slug)


def chapter_title(route: dict[str, object], slug: str) -> str:
    number = route["chapters"].index(slug) + 1
    fork = route.get("fork")
    if fork:
        for choice in fork["choices"]:
            if choice["chapter"] == slug:
                return f"{route['shortLabel']} Ending · {choice['label']}"
    return f"{route['shortLabel']} Voyage · Chapter {number:02d}"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def build(translation_root: Path, output_root: Path) -> dict[str, object]:
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    chapter_entries: list[dict[str, object]] = []
    total_lines = 0
    common_final_background: int | None = None

    for route in ROUTES:
        current_background = None if route["id"] == "common" else common_final_background
        for slug in route["chapters"]:
            batch = batch_directory(translation_root, slug)
            input_path = batch / "input.tsv"
            output_path = batch / "output.tsv"
            if not input_path.is_file() or not output_path.is_file():
                raise FileNotFoundError(f"Missing translation batch for {slug}: {batch}")

            source_rows = read_tsv(input_path)
            targets = {row["line_id"]: row for row in read_tsv(output_path)}
            backgrounds, current_background = visual_transitions(
                translation_root / "work" / "xfl-roundtrip-unpacked" / f"{slug}.gsc",
                current_background,
            )
            lines: list[dict[str, object]] = []
            for position, source in enumerate(source_rows, start=1):
                target = targets.get(source["line_id"])
                if target is None:
                    raise ValueError(f"Missing target row {source['line_id']}")
                speaker_jp = source.get("speaker_source", "").strip()
                line = {
                    "id": source["line_id"],
                    "i": position,
                    "t": source.get("row_type", "monologue"),
                    "sj": speaker_jp,
                    "se": SPEAKERS.get(speaker_jp, speaker_jp),
                    "jp": normalize_text(source.get("source_text", "")),
                    "en": normalize_text(target.get("target_text", "")),
                }
                if position in backgrounds:
                    line["bg"] = f"assets/backgrounds/{backgrounds[position]:04d}.webp"
                lines.append(line)

            title = chapter_title(route, slug)
            chapter_data = {
                "slug": slug,
                "route": route["id"],
                "title": title,
                "titleArt": f"assets/chapter-titles/{slug}.webp",
                "lines": lines,
            }
            write_json(output_root / "chapters" / f"{slug}.json", chapter_data)
            chapter_entries.append(
                {
                    "slug": slug,
                    "route": route["id"],
                    "title": title,
                    "lineCount": len(lines),
                    "titleArt": chapter_data["titleArt"],
                }
            )
            total_lines += len(lines)
        if route["id"] == "common":
            common_final_background = current_background

    payload = {
        "generatedAt": generated_at,
        "chapterCount": len(chapter_entries),
        "lineCount": total_lines,
        "routes": ROUTES,
        "chapters": chapter_entries,
    }
    write_json(output_root / "index.json", payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translation-root", type=Path, default=DEFAULT_TRANSLATION_ROOT)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build(args.translation_root.resolve(), args.output_root.resolve())
    print(
        json.dumps(
            {
                "chapters": result["chapterCount"],
                "lines": result["lineCount"],
                "output": str(args.output_root.resolve()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
