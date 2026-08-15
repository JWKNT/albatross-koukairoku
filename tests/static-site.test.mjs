import assert from "node:assert/strict";
import { readFile, readdir, stat } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const read = (path) => readFile(new URL(path, root), "utf8");

test("page exposes the minimal route-aware reader controls", async () => {
  const html = await read("index.html");
  assert.match(html, /Albatross Koukairoku Script Reader/);
  assert.match(html, /href="\/site-theme\/v1\/base\.css"/);
  assert.match(html, /src="\/site-theme\/v1\/theme\.js"/);
  assert.match(html, /id="route-select"/);
  assert.match(html, /value="route"/);
  assert.match(html, /English reader/);
  assert.doesNotMatch(html, /id="route-map"/);
});

test("empty URL hashes cannot trigger the chapter-load error state", async () => {
  const script = await read("assets/app.js");
  assert.match(script, /window\.location\.hash \? document\.querySelector/);
  assert.doesNotMatch(script, /window\.location\.hash && document\.querySelector/);
});

test("index covers every canonical route and chapter", async () => {
  const index = JSON.parse(await read("data/index.json"));
  assert.equal(index.routes.length, 5);
  assert.equal(index.chapterCount, 84);
  assert.equal(index.chapters.length, 84);
  assert.deepEqual(index.routes.map((route) => route.id), ["common", "kuro", "twins", "rui", "final"]);
  assert.equal(new Set(index.chapters.map((chapter) => chapter.slug)).size, 84);
  assert.ok(index.lineCount > 10_000);

  for (const route of index.routes) {
    for (const slug of route.chapters) {
      assert.ok(index.chapters.some((chapter) => chapter.slug === slug), `missing ${slug}`);
    }
  }
});

test("chapter JSON and title art exist for every index entry", async () => {
  const index = JSON.parse(await read("data/index.json"));
  const chapterFiles = new Set(await readdir(new URL("data/chapters/", root)));
  const titleFiles = new Set(await readdir(new URL("assets/chapter-titles/", root)));

  for (const meta of index.chapters) {
    assert.ok(chapterFiles.has(`${meta.slug}.json`), `missing chapter ${meta.slug}`);
    assert.ok(titleFiles.has(`${meta.slug}.webp`), `missing title ${meta.slug}`);
    const chapter = JSON.parse(await read(`data/chapters/${meta.slug}.json`));
    assert.equal(chapter.lines.length, meta.lineCount);
    assert.equal(chapter.lines[0].id.slice(0, 4), meta.slug);
    assert.ok(chapter.lines.every((line) => typeof line.en === "string" && line.en.length > 0));
  }
});

test("English reader backgrounds resolve to exported game art", async () => {
  const index = JSON.parse(await read("data/index.json"));
  const backgroundFiles = new Set(await readdir(new URL("assets/backgrounds/", root)));
  let transitionCount = 0;
  for (const meta of index.chapters) {
    const chapter = JSON.parse(await read(`data/chapters/${meta.slug}.json`));
    for (const line of chapter.lines) {
      if (!line.bg) continue;
      transitionCount += 1;
      assert.match(line.bg, /^assets\/backgrounds\/\d{4}\.webp$/);
      assert.ok(backgroundFiles.has(line.bg.split("/").at(-1)), `missing ${line.bg}`);
    }
  }
  assert.ok(transitionCount > 800, `expected the full visual event stream, got ${transitionCount}`);

  const script = await read("assets/app.js");
  assert.match(script, /makeBackgroundFigure/);
  assert.match(script, /if \(line\.bg\)/);
});

test("audited adult CGs have a reproducible censorship manifest", async () => {
  const manifest = JSON.parse(await read("assets/backgrounds/censored-images.json"));
  const backgroundFiles = new Set(await readdir(new URL("assets/backgrounds/", root)));

  assert.equal(manifest.count, 140);
  assert.equal(manifest.images.length, manifest.count);
  assert.equal(new Set(manifest.images).size, manifest.count);
  assert.match(manifest.method, /12x9 mosaic/);
  assert.match(manifest.method, /Gaussian blur radius 6/);
  for (const filename of manifest.images) {
    assert.match(filename, /^\d{4}\.webp$/);
    assert.ok(backgroundFiles.has(filename), `missing censored image ${filename}`);
    const metadata = await stat(new URL(`assets/backgrounds/${filename}`, root));
    assert.ok(metadata.size < 10 * 1024, `censorship appears absent from ${filename}`);
  }
});

test("branch points identify both endings", async () => {
  const index = JSON.parse(await read("data/index.json"));
  const expected = {
    kuro: ["2014", "2015"],
    twins: ["3017", "3018"],
    rui: ["4018", "4019"],
  };
  for (const [routeId, endings] of Object.entries(expected)) {
    const route = index.routes.find((candidate) => candidate.id === routeId);
    assert.deepEqual(route.fork.choices.map((choice) => choice.chapter), endings);
  }
});

test("all local page assets referenced by the shell exist", async () => {
  const html = await read("index.html");
  for (const path of ["assets/styles.css", "assets/app.js"]) {
    assert.match(html, new RegExp(path.replace(".", "\\.")));
    assert.ok((await read(path)).length > 1_000);
  }
});

test("repository exposes the complete verified game patcher", async () => {
  const readme = await read("README.md");
  assert.match(readme, /one-click complete game patcher/);
  for (const path of [
    "tools/albatross-complete-patcher/README.md",
    "tools/albatross-complete-patcher/install_albatross_patch.py",
    "tools/albatross-complete-patcher/delta_codec.py",
    "tools/albatross-complete-patcher/Install Albatross English Patch.command",
    "tools/albatross-complete-patcher/Install Albatross English Patch.bat",
  ]) {
    assert.ok((await read(path)).length > 100, `missing patcher component ${path}`);
  }
});

test("tools page mirrors the release download shell", async () => {
  const reader = await read("index.html");
  const tools = await read("tools.html");
  assert.match(reader, /href="tools\.html">Tools<\/a>/);
  assert.match(tools, /Albatross Koukairoku Tools/);
  assert.match(tools, /id="downloads"/);
  assert.match(tools, /class="tool-card"/);
  assert.match(tools, /albatross-complete-patcher-v1\.1\.1\.zip/);
  assert.match(tools, /releases\/tag\/albatross-english-patcher-v1\.1\.1/);
  assert.match(tools, /1a7217de581800dc60febad6fd59a7e6596d6c97f1aee711053b696572f449a0/);
});
