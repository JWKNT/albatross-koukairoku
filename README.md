# Albatross Koukairoku Script Reader

A static, route-aware Japanese/English reader for the current machine-assisted fan translation of raiL-soft's *Albatross Koukairoku*.

## Reader features

- Side-by-side Japanese/English comparison and an English-only reading mode.
- Common, Kuro, Sisam & Kisara, Rui, and final-voyage navigation.
- Explicit branch navigation for the two endings in each character voyage.
- Chapter, route, and whole-story search with stable line links.
- Original chapter title art and in-story backgrounds/CGs; audited adult CGs are
  published only as aggressive full-frame mosaics (see
  `assets/backgrounds/censored-images.json`).
- Responsive layouts, dark mode, and keyboard-accessible controls.

## Refreshing the site data

The generator reads the working translation at `/Users/jw/Desktop/local-work/albatross_MTL` by default:

```sh
npm run build:data
npm test
```

The site is plain HTML, CSS, JavaScript, and JSON so GitHub Pages can serve it directly from the repository root.

## Complete English game patch

The repository includes a [one-click complete game patcher](tools/albatross-complete-patcher/README.md)
that converts a verified fresh Japanese Windows copy into the current English
build without distributing the original game. It installs the complete
word-wrapped script, localized interface and gallery graphics, and horizontal
English layout. On macOS/CrossOver it also fixes fullscreen mode without
requiring an unavailable 800×600 display mode. Original files are verified and
retained for rollback.

## Disclaimer

This is an unofficial, noncommercial fan project. The English text is a machine-assisted draft and may change as review continues. Please support the creators and own a legal Japanese copy of the game.
