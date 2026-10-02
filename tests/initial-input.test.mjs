/* Browser input can change while the initial JSON requests are still pending. */
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';

for (const filename of ['app.js', 'glossary.js']) {
  const file = new URL(`../assets/${filename}`, import.meta.url);
  if (!existsSync(file)) continue;
  const source = readFileSync(file, 'utf8');
  const albatross = source.includes('async function initialize()');
  const name = albatross ? 'initialize' : 'init';
  const initSource = source.match(new RegExp(`  async function ${name}\\([^]*?\\n  }`))[0];
  for (const query of ['typed before loading', '']) test(`${filename} preserves ${query ? 'a typed query' : 'a cleared URL query'} during initial loading`, async () => {
    const search = { value: '' }, element = () => ({ textContent: '', hidden: false });
    const state = {};
    const elements = new Proxy({ search }, { get(target, key) { return target[key] ??= element(); } });
    let release;
    const pending = new Promise(resolve => { release = resolve; });
    const index = { generatedAt: '2026-01-01', chapters: [{ slug: 'a', route: 'one' }], chapterCount: 1, lineCount: 1, translatedLines: 1, updated: 'today' };
    const context = {
      state, elements, URLSearchParams, Date, Intl, Map,
      window: { location: { search: '?q=original&chapter=a' } },
      fetchJson: async path => { await pending; return path.includes('glossary') ? { groups: [] } : path.includes('progression') ? { vnOrder: ['a'] } : index; },
      localStorage: { getItem: () => null }, number: new Intl.NumberFormat(),
      chapterMeta: () => index.chapters[0], chapterPosition: () => 0, currentChapterOrder: () => index.chapters,
      document: { querySelector: () => ({ checked: false }) },
      buildChapterMenu() {}, buildRouteSelect() {}, updateChapterControls() {}, updateSearchPlaceholder() {}, updateReadingMode() {}, bindEvents() {}, updateUrl() {}, populateChapterMenu() {}, populateChapters() {}, render() {},
      renderCurrentChapter: async () => {}, changeChapter: async () => {},
      console: { error(error) { throw error; } },
    };
    vm.createContext(context); vm.runInContext(initSource, context);
    const loading = context[name]();
    assert.equal(search.value, 'original', 'the shared URL is applied before loading');
    search.value = query;
    release(); await loading;
    assert.equal(search.value, query);
    assert.equal(state.query, query);
  });
}
