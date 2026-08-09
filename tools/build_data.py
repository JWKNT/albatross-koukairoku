#!/usr/bin/env python3
"""Build compact route-aware reader data from the Albatross MTL workspace."""

from __future__ import annotations

import argparse
import csv
import json
import re
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


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def normalize_text(value: str) -> str:
    return CONTROL_RE.sub("\n", value or "").replace("\r\n", "\n").strip()


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

    for route in ROUTES:
        for slug in route["chapters"]:
            batch = batch_directory(translation_root, slug)
            input_path = batch / "input.tsv"
            output_path = batch / "output.tsv"
            if not input_path.is_file() or not output_path.is_file():
                raise FileNotFoundError(f"Missing translation batch for {slug}: {batch}")

            source_rows = read_tsv(input_path)
            targets = {row["line_id"]: row for row in read_tsv(output_path)}
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
