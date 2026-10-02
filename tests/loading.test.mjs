/* Execute the production async functions with controlled network completion.
   This covers state/DOM behavior; browser layout is reviewed separately. */
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import test from 'node:test';
const source = readFileSync(new URL('../assets/app.js', import.meta.url), 'utf8');
const albatross = source.includes('async function renderCurrentChapter(');
const renderName = albatross ? 'renderCurrentChapter' : 'render';
function extract(name) {
  const value = source.match(new RegExp(`  (?:async )?function ${name}\\([^]*?\\n  }`))?.[0];
  assert.ok(value, `production ${name} function exists`);
  return value;
}
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };

function cacheHarness() {
  const requests = [];
  const context = { state: { cache: new Map(), index: { generatedAt: 'version' } }, fetchJson: path => { const r = deferred(); requests.push({ ...r, path }); return r.promise; } };
  vm.createContext(context); vm.runInContext(extract('loadChapter'), context);
  return { ...context, requests };
}

test('concurrent chapter loads share one request and successful content stays cached', async () => {
  const h = cacheHarness();
  const first = h.loadChapter('one'), second = h.loadChapter('one');
  assert.equal(h.requests.length, 1);
  const data = { slug: 'one', lines: [] }; h.requests[0].resolve(data);
  assert.equal(await first, data); assert.equal(await second, data);
  assert.equal(await h.loadChapter('one'), data);
  assert.equal(h.requests.length, 1);
});

test('a failed chapter load is evicted so the next interaction can retry', async () => {
  const h = cacheHarness();
  const first = h.loadChapter('one');
  h.requests[0].reject(new Error('Temporary network failure'));
  await assert.rejects(first, /Temporary network failure/);
  assert.equal(h.state.cache.has('one'), false);
  const retry = h.loadChapter('one');
  assert.equal(h.requests.length, 2);
  const data = { slug: 'one', lines: [] }; h.requests[1].resolve(data);
  assert.equal(await retry, data);
});

function renderHarness() {
  const requests = new Map(), parts = { h2: { textContent: 'No matching lines' }, p: { textContent: 'Try a broader search or another chapter.' } };
  const element = () => ({ hidden: false, textContent: '', value: '', children: [], replaceChildren(...children) { this.children = children; } });
  const elements = Object.fromEntries(['resultStatus', 'chapterTitle', 'chapterProgress', 'scriptLines', 'emptyState', 'clearSearch', 'search', 'portraitStage'].map(key => [key, element()]));
  elements.emptyState.querySelector = name => parts[name];
  const meta = id => ({ slug: id, title: id, lineCount: 1 });
  const state = { chapter: 'a', searchToken: 0, scope: 'chapter', query: '', index: { chapters: [meta('a'), meta('b')] } };
  const context = {
    state, elements, MAX_RESULTS: 500, number: new Intl.NumberFormat('en-US'),
    chapterMeta: (id = state.chapter) => meta(id), routeMeta: () => ({ chapters: ['a', 'b'] }),
    queryTerms: () => state.query ? [state.query] : [], matches: () => true,
    loadChapter: id => { const r = deferred(); requests.set(id, r); return r.promise; },
    makeLineArticle: line => line, makeBackgroundFigure: () => null,
    updateChapterControls() {}, updateUrl() {}, schedulePortraitUpdate() {},
    window: { location: { hash: '' } }, console: { error() {} },
    renderGroups: groups => { const lines = groups.flatMap(group => group.lines); elements.scriptLines.replaceChildren(...lines); elements.emptyState.hidden = lines.length > 0; },
  };
  vm.createContext(context); vm.runInContext(extract(renderName), context);
  return { ...context, render: context[renderName], requests, parts };
}

test('a stale chapter failure cannot clear a more recently loaded chapter', async () => {
  const h = renderHarness();
  const first = h.render();
  h.state.chapter = 'b'; const latest = h.render();
  const line = { id: 'b-1', en: 'Current chapter' };
  h.requests.get('b').resolve({ slug: 'b', lines: [line] }); await latest;
  h.requests.get('a').reject(new Error('Old interrupted request')); await first;
  assert.deepEqual(h.elements.scriptLines.children, [line]);
  assert.equal(h.elements.emptyState.hidden, true);
});

test('a successful empty search restores its normal message after a load failure', async () => {
  const h = renderHarness();
  const first = h.render(); h.requests.get('a').reject(new Error('Temporary failure')); await first;
  assert.equal(h.parts.h2.textContent, 'The script could not be loaded');
  h.state.query = 'unmatched'; const retry = h.render();
  h.requests.get('a').resolve({ slug: 'a', lines: [] }); await retry;
  assert.equal(h.elements.emptyState.hidden, false);
  assert.equal(h.parts.h2.textContent, 'No matching lines');
  assert.equal(h.parts.p.textContent, 'Try a broader search or another chapter.');
});
