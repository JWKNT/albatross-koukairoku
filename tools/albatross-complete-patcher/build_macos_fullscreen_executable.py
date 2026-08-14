#!/usr/bin/env python3
"""Build the verified macOS/CrossOver fullscreen-compatible game executable."""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
from pathlib import Path


SOURCE_SHA256 = "f04c9729c0f60269f6ffdc63ea71c587a2431c501ade698e374978050fd156c4"
TARGET_SHA256 = "9b90cbf8189e5238b0fc65dc3a7ea483ed7f5de6203174d2d487f6a05fc15b7e"
PATCH_BLOB = bytes.fromhex(
    "31c0c20800837c241c210f85a7000000837c2414000f859c000000837c241800"
    "0f85910000005589e583ec18535657ff150c3247008d4df05150ff1508324700"
    "85c074688b5df82b5df08b75fc2b75f489d86bc00389f1c1e10239c87e1489"
    "f031d2b903000000f7f1c1e00289c789f0eb0a89df89d86bc003c1e802897d"
    "ec8945e889d929f9d1f9034df089f229c2d1fa0355f46a60ff75e8ff75ec52"
    "51ff750cff7508ff1510324700eb0231c05f5e5b89ec5dc21c00ff2510324700"
)
CALLS = (
    (0x4DE45, 0x44DE45, 0x472C30, bytes.fromhex("ff1518324700")),
    (0x4DF93, 0x44DF93, 0x472C35, bytes.fromhex("ff1510324700")),
)


def digest(data: bytes | bytearray) -> str:
    return hashlib.sha256(data).hexdigest()


def build(source: Path, output: Path) -> None:
    data = bytearray(source.read_bytes())
    if digest(data) != SOURCE_SHA256:
        raise ValueError(f"unsupported game executable: {source}")
    if struct.unpack_from("<I", data, 0x1F8)[0] != 0x71C22:
        raise ValueError("unexpected .text virtual size")
    struct.pack_into("<I", data, 0x1F8, 0x72000)
    cave = slice(0x72C30, 0x72C30 + len(PATCH_BLOB))
    if any(data[cave]):
        raise ValueError("verified executable code cave is not empty")
    data[cave] = PATCH_BLOB
    for offset, address, target, expected in CALLS:
        if data[offset : offset + 6] != expected:
            raise ValueError(f"unexpected instruction at file offset 0x{offset:X}")
        relative = target - (address + 5)
        data[offset : offset + 6] = b"\xE8" + struct.pack("<i", relative) + b"\x90"
    if digest(data) != TARGET_SHA256:
        raise ValueError("fullscreen executable did not match its verified target")
    temporary = output.with_name(output.name + ".albatross-building")
    if temporary.exists():
        raise FileExistsError(temporary)
    temporary.write_bytes(data)
    os.replace(temporary, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
