# Complete English game patcher

This patcher converts a verified fresh Windows copy of *Albatross Koukairoku*
into the complete English build. It installs:

- the fully translated and English-word-wrapped scenario archive;
- localized chapter titles, configuration, save/load, and toolbar graphics;
- English title-screen and Extras navigation in every interaction state;
- localized gallery headings, captions, locked tile, and music titles;
- the engine's native horizontal-writing preference.

The release contains binary differences, not the original game. You must own a
compatible Japanese Windows copy. Every source archive is verified before any
game file is changed, every rebuilt target is hash-checked in staging, and the
original archives are retained for rollback.

## One-click installation

1. Download and extract the release archive.
2. On macOS/CrossOver, double-click **Install Albatross English Patch.command**.
   On Windows, double-click **Install Albatross English Patch.bat**.
3. Drag the folder containing `信天翁航海録.exe` into the terminal window and
   press Return. You can also drag the folder or executable onto the launcher.
4. Launch the game normally after the installer reports `Finished`.

Python 3.9 or newer is the only patch-time requirement. The installer needs
temporary free space for the five rebuilt archives. Original Japanese archives
are retained under `AlbatrossEnglish/backup` so installation can be verified,
updated, or restored without redistributing game data.

## Command line

```sh
python3 install_albatross_patch.py "/path/to/Albatross Koukairoku"
python3 install_albatross_patch.py --verify "/path/to/Albatross Koukairoku"
python3 install_albatross_patch.py --update "/path/to/Albatross Koukairoku"
python3 install_albatross_patch.py --restore "/path/to/Albatross Koukairoku"
```

Running the installer again verifies the retained Japanese sources and updates
the English archives in place. Save progress is preserved. Restore changes only
the two-byte writing-direction preference rather than replacing the save file.

## Maintainer workflow

Build payloads from an immutable Japanese runtime and the validated English
runtime:

```sh
python3 build_deltas.py /path/to/japanese /path/to/current
python3 build_release.py --version 1.0.0 --output /path/to/release.zip
```

`delta_codec.py` uses content-defined chunks and split zlib literal streams.
The build report records exact source and target hashes for all five archives.
