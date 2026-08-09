import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const read = (path) => readFile(new URL(path, root), "utf8");

test("page exposes the minimal route-aware reader controls", async () => {
  const html = await read("index.html");
  assert.match(html, /Albatross Koukairoku Script Reader/);
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
