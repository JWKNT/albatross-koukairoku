# Albatross Koukairoku Script Reader

A static, route-aware Japanese/English reader for the current machine-assisted fan translation of raiL-soft's *Albatross Koukairoku*.

## Reader features

- Side-by-side Japanese/English comparison and an English-only reading mode.
- Common, Kuro, Sisam & Kisara, Rui, and final-voyage navigation.
- Explicit branch navigation for the two endings in each character voyage.
- Chapter, route, and whole-story search with stable line links.
- Spoiler-light original chapter title art and an original game UI background.
- Responsive layouts, dark mode, and keyboard-accessible controls.

## Refreshing the site data

The generator reads the working translation at `/Users/jw/Desktop/bin/albatross_MTL` by default:

```sh
npm run build:data
npm test
```

The site is plain HTML, CSS, JavaScript, and JSON so GitHub Pages can serve it directly from the repository root.

## Disclaimer

This is an unofficial, noncommercial fan project. The English text is a machine-assisted draft and may change as review continues. Please support the creators and own a legal Japanese copy of the game.
