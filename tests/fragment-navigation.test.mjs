import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const source = readFileSync(new URL('../assets/app.js', import.meta.url), 'utf8');
const extract = (text, name) => {
  const fn = text.match(new RegExp(`  (?:async )?function ${name}\\([^]*?\\n  }`))?.[0];
  assert.ok(fn, `${name} exists`); return fn;
};
for (const file of ['app.js', 'glossary.js']) {
  const path = new URL(`../assets/${file}`, import.meta.url);
  if (!existsSync(path)) continue;
  test(`${file} treats URL fragments as IDs, safely decoding or ignoring malformed input`, () => {
    const actualSource = readFileSync(path, 'utf8');
    const target = {};
    const context = { window: { location: { hash: '' } }, document: { getElementById: id => id === 'line-A1-0005' ? target : null } };
    vm.createContext(context); vm.runInContext(extract(actualSource, 'fragmentTarget'), context);
    for (const hash of ['', '#[', '#%', '#missing']) { context.window.location.hash = hash; assert.equal(context.fragmentTarget(), null, hash); }
    for (const hash of ['#line-A1-0005', '#line%2DA1%2D0005']) { context.window.location.hash = hash; assert.equal(context.fragmentTarget(), target, hash); }
    assert.doesNotMatch(actualSource, /querySelector\(window\.location\.hash\)/);
  });
}

test('URL updates retain a current line link but remove a previous chapter fragment', () => {
  const state = { chapter: 'A1', query: '', scope: 'chapter', mode: 'parallel', order: 'vn' };
  let replaced;
  const context = { state, URL, window: { location: { href: 'https://example.test/?chapter=A1#line-A1-0005' } }, elements: { glossaryLink: {} }, history: { replaceState: (_state, _title, href) => { replaced = href; } } };
  vm.createContext(context); vm.runInContext(extract(source, 'updateUrl'), context);
  context.updateUrl(); assert.equal(new URL(replaced, 'https://example.test/').hash, '#line-A1-0005');
  state.chapter = 'B1'; context.updateUrl(); assert.equal(new URL(replaced, 'https://example.test/').hash, '');
  context.window.location.href = 'https://example.test/#line-B1-0005';
  context.updateUrl(); assert.equal(new URL(replaced, 'https://example.test/').hash, '#line-B1-0005');
});

if (source.includes('async function changeChapter(')) test('a superseded chapter change cannot scroll after the newer view is ready', async () => {
  const pending = [], scrolls = [], state = { chapter: 'A1', searchToken: 0 };
  const context = { state, chapterMeta: slug => ({ slug }), updateChapterControls() {}, setChapterHeading() {}, document: { querySelector: selector => ({ scrollIntoView: () => scrolls.push(selector) }) }, render: () => { ++state.searchToken; return new Promise(resolve => pending.push(resolve)); } };
  vm.createContext(context); vm.runInContext(extract(source, 'changeChapter'), context);
  const first = context.changeChapter('B1');
  const latest = context.changeChapter('C1', { scrollTo: '.script-heading' });
  pending[1](); await latest;
  assert.deepEqual(scrolls, ['.script-heading']);
  pending[0](); await first;
  assert.deepEqual(scrolls, ['.script-heading']);
});
