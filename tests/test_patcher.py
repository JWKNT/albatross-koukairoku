from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCHER = ROOT / "tools/albatross-complete-patcher"
sys.path.insert(0, str(PATCHER))

from delta_codec import apply_delta, create_delta, sha256  # noqa: E402
import install_albatross_patch as installer  # noqa: E402


class PatcherTests(unittest.TestCase):
    def test_dragged_paths(self) -> None:
        self.assertEqual(
            installer.parse_dragged_path(r"/Games/Albatross\ Koukairoku"),
            "/Games/Albatross Koukairoku",
        )
        self.assertEqual(
            installer.parse_dragged_path('"C:\\Games\\Albatross"', platform="win32"),
            "C:\\Games\\Albatross",
        )
        with self.assertRaises(ValueError):
            installer.parse_dragged_path("")

    def test_english_preferences_patch_preserves_other_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rssave.dat"
            before = bytearray((index * 17) % 256 for index in range(0x900))
            before[installer.DIRECTION_OFFSET : installer.DIRECTION_OFFSET + 2] = b"\0\0"
            before[installer.FONT_SIZE_OFFSET : installer.FONT_SIZE_OFFSET + 2] = b"\0\0"
            path.write_bytes(before)
            installer.write_english_preferences(path)
            after = path.read_bytes()
            self.assertEqual(len(after), len(before))
            self.assertEqual(
                after[installer.DIRECTION_OFFSET : installer.DIRECTION_OFFSET + 2],
                b"\x01\x00",
            )
            self.assertEqual(
                after[installer.FONT_SIZE_OFFSET : installer.FONT_SIZE_OFFSET + 2],
                b"\x01\x00",
            )
            self.assertEqual(installer.read_font_size(path), installer.MEDIUM_FONT)
            self.assertEqual(
                after[: installer.DIRECTION_OFFSET], before[: installer.DIRECTION_OFFSET]
            )
            self.assertEqual(
                after[installer.FONT_SIZE_OFFSET + 2 :],
                before[installer.FONT_SIZE_OFFSET + 2 :],
            )

    def test_single_preference_write_preserves_other_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rssave.dat"
            before = bytearray((index * 13) % 256 for index in range(0x900))
            before[installer.DIRECTION_OFFSET : installer.DIRECTION_OFFSET + 2] = b"\1\0"
            before[installer.FONT_SIZE_OFFSET : installer.FONT_SIZE_OFFSET + 2] = b"\2\0"
            path.write_bytes(before)
            installer.write_preference(
                path, installer.DIRECTION_OFFSET, installer.LARGE_FONT
            )
            after = path.read_bytes()
            self.assertEqual(installer.read_direction(path), installer.LARGE_FONT)
            self.assertEqual(installer.read_font_size(path), installer.SMALL_FONT)
            self.assertEqual(
                after[installer.FONT_SIZE_OFFSET :], before[installer.FONT_SIZE_OFFSET :]
            )

    def test_delta_round_trip_and_source_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.bin"
            target = root / "target.bin"
            patch = root / "patch"
            output = root / "output.bin"
            data = bytearray((index * 29 + 7) % 256 for index in range(320_000))
            source.write_bytes(data)
            replacement = (b"English Albatross " * 2_500)[:40_000]
            data[90_000:130_000] = replacement
            target.write_bytes(data)
            manifest = create_delta(source, target, patch)
            apply_delta(source, patch, output)
            self.assertEqual(sha256(output), sha256(target))
            self.assertGreater(manifest["copied_bytes"], 0)
            source.write_bytes(source.read_bytes() + b"corrupt")
            with self.assertRaises(ValueError):
                apply_delta(source, patch, root / "rejected.bin")

    def test_release_payload_covers_every_runtime_archive(self) -> None:
        report_path = PATCHER / "payload/build-report.json"
        self.assertTrue(report_path.is_file(), "maintainer payload has not been built")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["format"], "albatross-complete-patcher-payload-v1")
        self.assertEqual(set(report["files"]), set(installer.PATCHES.values()))
        payload = installer.manifests(include_all=True)
        self.assertEqual(set(payload), set(installer.PATCHES))
        for details in payload.values():
            self.assertEqual(details["format"], "albatross-delta-v1")
            self.assertNotEqual(details["source_sha256"], details["target_sha256"])

    def test_platform_patch_selection(self) -> None:
        self.assertEqual(
            set(installer.selected_patches("win32")),
            set(installer.ARCHIVE_PATCHES),
        )
        self.assertEqual(
            set(installer.selected_patches("darwin")),
            set(installer.PATCHES),
        )

    def test_verified_fullscreen_executable_builder(self) -> None:
        module_path = PATCHER / "build_macos_fullscreen_executable.py"
        spec = importlib.util.spec_from_file_location("fullscreen_builder", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source_manifest = installer.manifests(include_all=True)[installer.GAME_EXE]
        self.assertEqual(module.SOURCE_SHA256, source_manifest["source_sha256"])
        self.assertEqual(module.TARGET_SHA256, source_manifest["target_sha256"])


if __name__ == "__main__":
    unittest.main()
