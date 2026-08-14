#!/usr/bin/env python3
"""Install, update, verify, or restore the complete Albatross English patch."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
import time
from pathlib import Path

from delta_codec import apply_delta, sha256


VERSION = "1.1.0"
PATCHER = Path(__file__).resolve().parent
PAYLOAD = PATCHER / "payload"
GAME_EXE = "信天翁航海録.exe"
STATE_NAME = "AlbatrossEnglish"
STAGING_NAME = ".albatross-patcher-staging"
SAVE_RELATIVE = Path("save/rssave.dat")
DIRECTION_OFFSET = 0x84A
HORIZONTAL = 1
ARCHIVE_PATCHES = {
    "scr.xfl": "english-scr",
    "grps.xfl": "english-grps",
    "grpo.xfl": "english-grpo",
    "grpe.xfl": "english-grpe",
    "grpo_ex.xfl": "english-grpo-ex",
}
MACOS_PATCHES = {GAME_EXE: "macos-fullscreen-exe"}
PATCHES = {**ARCHIVE_PATCHES, **MACOS_PATCHES}


def selected_patches(platform: str | None = None) -> dict[str, str]:
    patches = dict(ARCHIVE_PATCHES)
    if (platform or sys.platform) == "darwin":
        patches.update(MACOS_PATCHES)
    return patches


def normalized_game_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if path.is_file():
        path = path.parent
    return path


def parse_dragged_path(value: str, platform: str | None = None) -> str:
    value = value.strip()
    if not value:
        raise ValueError("No game folder was supplied")
    if (platform or sys.platform) == "win32":
        return value.strip('"').strip("'")
    try:
        values = shlex.split(value)
    except ValueError as error:
        raise ValueError(f"Could not read the dragged game path: {error}") from error
    if len(values) != 1:
        raise ValueError("Please drag exactly one game folder into the prompt")
    return values[0]


def discover_game(argument: Path | None) -> Path:
    if argument is not None:
        return normalized_game_path(argument)
    print("Drag the Albatross Koukairoku game folder here, then press Return:")
    return normalized_game_path(parse_dragged_path(input("> ")))


def manifests(*, include_all: bool = False) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    patches = PATCHES if include_all else selected_patches()
    for filename, patch_name in patches.items():
        path = PAYLOAD / patch_name / "manifest.json"
        if not path.is_file():
            raise FileNotFoundError(f"Patch payload is incomplete: {path}")
        details = json.loads(path.read_text(encoding="utf-8"))
        if details.get("format") != "albatross-delta-v1":
            raise ValueError(f"Unsupported patch payload: {path}")
        result[filename] = details
    return result


def validate_game_shell(game: Path) -> None:
    executable = game / GAME_EXE
    if not executable.is_file() or executable.read_bytes()[:2] != b"MZ":
        raise ValueError(
            f"{game} is not a Windows Albatross Koukairoku installation "
            f"({GAME_EXE} is required)"
        )
    for filename in ARCHIVE_PATCHES:
        if not (game / filename).is_file():
            raise ValueError(f"Game archive is missing: {game / filename}")
    save = game / SAVE_RELATIVE
    if not save.is_file() or save.stat().st_size < DIRECTION_OFFSET + 2:
        raise ValueError(f"Game preferences are missing or unsupported: {save}")


def source_backups(game: Path) -> dict[str, Path]:
    backup = game / STATE_NAME / "backup"
    return {
        filename: backup / f"{filename}.original"
        for filename in selected_patches()
    }


def validate_backups(game: Path, payload: dict[str, dict[str, object]]) -> dict[str, Path]:
    backups = source_backups(game)
    for filename, source in backups.items():
        expected = payload[filename]
        if (
            not source.is_file()
            or source.stat().st_size != int(expected["source_size"])
            or sha256(source) != expected["source_sha256"]
        ):
            raise ValueError(f"Original rollback source is missing or corrupt: {source}")
    return backups


def migrate_missing_backups(
    game: Path, payload: dict[str, dict[str, object]]
) -> None:
    """Add files introduced by a newer patcher to an existing rollback set."""
    for filename, backup in source_backups(game).items():
        if backup.exists():
            continue
        current = game / filename
        expected = payload[filename]
        if not current.is_file() or sha256(current) != expected["source_sha256"]:
            raise ValueError(
                f"Cannot add rollback source for the new patch component: {current}"
            )
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current, backup)
        if sha256(backup) != expected["source_sha256"]:
            raise IOError(f"Rollback source migration failed: {backup}")


def archive_state(
    game: Path, payload: dict[str, dict[str, object]]
) -> dict[str, str]:
    state: dict[str, str] = {}
    for filename, expected in payload.items():
        path = game / filename
        digest = sha256(path)
        if digest == expected["source_sha256"]:
            state[filename] = "japanese"
        elif digest == expected["target_sha256"]:
            state[filename] = "english-current"
        else:
            state[filename] = "unknown"
    return state


def read_direction(path: Path) -> int:
    data = path.read_bytes()
    if len(data) < DIRECTION_OFFSET + 2:
        raise ValueError(f"Preferences file is too short: {path}")
    return int.from_bytes(data[DIRECTION_OFFSET : DIRECTION_OFFSET + 2], "little")


def write_direction(path: Path, value: int) -> None:
    data = bytearray(path.read_bytes())
    if len(data) < DIRECTION_OFFSET + 2:
        raise ValueError(f"Preferences file is too short: {path}")
    data[DIRECTION_OFFSET : DIRECTION_OFFSET + 2] = int(value).to_bytes(2, "little")
    temporary = path.with_name(path.name + ".albatross-installing")
    if temporary.exists():
        raise FileExistsError(f"Temporary preference file already exists: {temporary}")
    temporary.write_bytes(data)
    os.replace(temporary, path)
    if read_direction(path) != value:
        raise IOError(f"Writing-direction update failed: {path}")


def build_staging(
    sources: dict[str, Path], staging: Path
) -> dict[str, dict[str, object]]:
    if staging.exists():
        raise FileExistsError(f"Remove interrupted staging first: {staging}")
    staging.mkdir()
    results: dict[str, dict[str, object]] = {}
    for filename, patch_name in selected_patches().items():
        print(f"  Rebuilding English {filename}...")
        results[filename] = apply_delta(
            sources[filename], PAYLOAD / patch_name, staging / filename
        )
    return results


def rollback_fresh_commit(game: Path) -> None:
    backups = source_backups(game)
    for filename, original in backups.items():
        if original.is_file():
            os.replace(original, game / filename)
    state = game / STATE_NAME
    backup = state / "backup"
    if backup.is_dir() and not any(backup.iterdir()):
        backup.rmdir()
    if state.is_dir() and not any(state.iterdir()):
        state.rmdir()


def install_fresh(
    game: Path, payload: dict[str, dict[str, object]]
) -> dict[str, object]:
    if (game / STATE_NAME).exists():
        raise ValueError(f"Existing patch metadata blocks a fresh install: {game / STATE_NAME}")
    original_direction = read_direction(game / SAVE_RELATIVE)
    staging = game / STAGING_NAME
    patches = selected_patches()
    sources = {filename: game / filename for filename in patches}
    results = build_staging(sources, staging)
    state = game / STATE_NAME
    backup = state / "backup"
    committed = False
    try:
        backup.mkdir(parents=True)
        for filename in patches:
            os.replace(game / filename, backup / f"{filename}.original")
        for filename in patches:
            os.replace(staging / filename, game / filename)
        write_direction(game / SAVE_RELATIVE, HORIZONTAL)
        report = installation_report(
            game, payload, results, original_direction, operation="fresh-install"
        )
        (state / "install-report.json").write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        committed = True
        return report
    except Exception:
        if not committed:
            rollback_fresh_commit(game)
            write_direction(game / SAVE_RELATIVE, original_direction)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def update_installed(
    game: Path, payload: dict[str, dict[str, object]]
) -> dict[str, object]:
    migrate_missing_backups(game, payload)
    backups = validate_backups(game, payload)
    report_path = game / STATE_NAME / "install-report.json"
    previous_report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else {}
    )
    original_direction = int(previous_report.get("original_direction", 0))
    current_direction = read_direction(game / SAVE_RELATIVE)
    state = archive_state(game, payload)
    if set(state.values()) == {"english-current"}:
        write_direction(game / SAVE_RELATIVE, HORIZONTAL)
        report = installation_report(
            game, payload, {}, original_direction, operation="already-current"
        )
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print("The English patch files are already current.")
        return report

    staging = game / STAGING_NAME
    results = build_staging(backups, staging)
    rollback = staging / "previous"
    rollback.mkdir()
    replaced: list[str] = []
    try:
        for filename in selected_patches():
            os.replace(game / filename, rollback / filename)
            replaced.append(filename)
            os.replace(staging / filename, game / filename)
        write_direction(game / SAVE_RELATIVE, HORIZONTAL)
        report = installation_report(
            game, payload, results, original_direction, operation="update"
        )
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return report
    except Exception:
        for filename in reversed(replaced):
            previous = rollback / filename
            if previous.is_file():
                os.replace(previous, game / filename)
        if read_direction(game / SAVE_RELATIVE) != current_direction:
            write_direction(game / SAVE_RELATIVE, current_direction)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def installation_report(
    game: Path,
    payload: dict[str, dict[str, object]],
    results: dict[str, dict[str, object]],
    original_direction: int,
    *,
    operation: str,
) -> dict[str, object]:
    files = {filename: sha256(game / filename) for filename in selected_patches()}
    for filename, details in payload.items():
        if files[filename] != details["target_sha256"]:
            raise ValueError(f"Installed archive failed verification: {filename}")
    return {
        "format": f"albatross-complete-patch-v{VERSION}",
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "operation": operation,
        "game": str(game),
        "writing_direction": "horizontal",
        "macos_fullscreen_compatibility": sys.platform == "darwin",
        "writing_direction_offset": f"0x{DIRECTION_OFFSET:X}",
        "original_direction": original_direction,
        "files": files,
        "delta_targets": {
            filename: details["target_sha256"] for filename, details in payload.items()
        },
        "rebuilt": sorted(results),
    }


def verify_installed(game: Path) -> dict[str, object]:
    validate_game_shell(game)
    payload = manifests()
    validate_backups(game, payload)
    state = archive_state(game, payload)
    issues = [filename for filename, value in state.items() if value != "english-current"]
    if read_direction(game / SAVE_RELATIVE) != HORIZONTAL:
        issues.append(str(SAVE_RELATIVE))
    result = {
        "status": "CLEAN" if not issues else "FAILED",
        "game": str(game),
        "files": state,
        "writing_direction": read_direction(game / SAVE_RELATIVE),
        "issues": issues,
    }
    if issues:
        raise ValueError(f"Installed patch verification failed: {issues}")
    return result


def restore(game: Path) -> dict[str, object]:
    validate_game_shell(game)
    payload = manifests()
    migrate_missing_backups(game, payload)
    backups = validate_backups(game, payload)
    state = game / STATE_NAME
    report_path = state / "install-report.json"
    report = (
        json.loads(report_path.read_text(encoding="utf-8"))
        if report_path.is_file()
        else {}
    )
    original_direction = int(report.get("original_direction", 0))
    current_direction = read_direction(game / SAVE_RELATIVE)
    staging = game / ".albatross-restore-staging"
    if staging.exists():
        raise FileExistsError(f"Remove interrupted restore staging first: {staging}")
    staging.mkdir()
    rollback = staging / "current"
    rollback.mkdir()
    replaced: list[str] = []
    try:
        for filename, source in backups.items():
            shutil.copy2(source, staging / filename)
            if sha256(staging / filename) != payload[filename]["source_sha256"]:
                raise IOError(f"Restore staging verification failed: {filename}")
        for filename in selected_patches():
            os.replace(game / filename, rollback / filename)
            replaced.append(filename)
            os.replace(staging / filename, game / filename)
        write_direction(game / SAVE_RELATIVE, original_direction)
        retained = game / f"{STATE_NAME}.patcher-backup-{time.strftime('%Y%m%d-%H%M%S')}"
        if retained.exists():
            raise FileExistsError(f"Restore metadata destination already exists: {retained}")
        os.replace(state, retained)
        return {
            "status": "RESTORED",
            "game": str(game),
            "writing_direction": original_direction,
            "retained_metadata": str(retained),
        }
    except Exception:
        for filename in reversed(replaced):
            previous = rollback / filename
            if previous.is_file():
                os.replace(previous, game / filename)
        if read_direction(game / SAVE_RELATIVE) != current_direction:
            write_direction(game / SAVE_RELATIVE, current_direction)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def install_or_update(game: Path, require_update: bool = False) -> dict[str, object]:
    validate_game_shell(game)
    payload = manifests()
    state = archive_state(game, payload)
    values = set(state.values())
    metadata = game / STATE_NAME
    if values == {"japanese"} and not metadata.exists():
        if require_update:
            raise ValueError("--update requires an existing AlbatrossEnglish install")
        print("Building and verifying the complete English patch...")
        return install_fresh(game, payload)
    if metadata.is_dir():
        print("Verifying and updating the installed English patch...")
        return update_installed(game, payload)
    raise ValueError(
        "The game files are mixed or unsupported. No files were changed. "
        f"Detected states: {state}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path, nargs="?")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if sum((args.update, args.verify, args.restore)) > 1:
        parser.error("choose only one of --update, --verify, or --restore")
    try:
        game = discover_game(args.game)
        if args.verify:
            report = verify_installed(game)
        elif args.restore:
            report = restore(game)
        else:
            report = install_or_update(game, require_update=args.update)
    except (EOFError, FileNotFoundError, FileExistsError, OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
