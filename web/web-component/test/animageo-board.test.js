/**
 * <animageo-board> tests with a tiny DOM shim (no jsdom): verifies the element
 * builds from a spec property, surfaces runtime signals as CustomEvents,
 * delegates actions, and tears down on disconnect. The engine is injected.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

// ── minimal DOM shim, installed before importing the component ──────────────
class FakeEventTarget {
  constructor() {
    this._ls = {};
  }
  addEventListener(type, cb) {
    (this._ls[type] || (this._ls[type] = [])).push(cb);
  }
  removeEventListener(type, cb) {
    if (this._ls[type]) this._ls[type] = this._ls[type].filter((f) => f !== cb);
  }
  dispatchEvent(ev) {
    (this._ls[ev.type] || []).forEach((cb) => cb(ev));
    return true;
  }
}
class FakeHTMLElement extends FakeEventTarget {
  constructor() {
    super();
    this._attrs = {};
    this.isConnected = false;
  }
  getAttribute(n) {
    return n in this._attrs ? this._attrs[n] : null;
  }
  setAttribute(n, v) {
    this._attrs[n] = String(v);
  }
  appendChild() {}
  querySelector() {
    return null;
  }
}
globalThis.HTMLElement = FakeHTMLElement;
globalThis.CustomEvent = class {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
    this.bubbles = !!init.bubbles;
    this.composed = !!init.composed;
  }
};
const _registry = new Map();
globalThis.customElements = {
  define: (n, c) => _registry.set(n, c),
  get: (n) => _registry.get(n),
};

const { AnimageoBoard } = await import('../src/animageo-board.js');
const { mockEngine, sampleSpec } = await import('../../runtime/test/mock-engine.js');

function connected(spec = sampleSpec()) {
  const el = new AnimageoBoard();
  el.engine = mockEngine();
  el.isConnected = true;
  el.spec = spec; // setter triggers a synchronous rebuild (engine injected)
  return el;
}

test('registers the custom element', () => {
  assert.equal(customElements.get('animageo-board'), AnimageoBoard);
});

test('builds from a spec property and delegates getState', () => {
  const el = connected();
  assert.ok(el.handle, 'handle created');
  assert.deepEqual(el.getState(), { A: { x: -2, y: -1 }, k: 3 });
});

test('setState / setValue delegate to the handle', () => {
  const el = connected();
  el.setState({ A: { x: 1, y: 1 } });
  assert.deepEqual(el.getState().A, { x: 1, y: 1 });
  el.setValue('k', 6);
  assert.equal(el.getState().k, 6);
});

test('dispatches animageo:change on drag and animageo:commit on up', () => {
  const el = connected();
  const changes = [];
  const commits = [];
  el.addEventListener('animageo:change', (e) => changes.push(e.detail));
  el.addEventListener('animageo:commit', (e) => commits.push(e.detail));

  el.handle.S.A._x = 3;
  el.handle.S.A._y = 4;
  el.handle.S.A._fire('drag');
  el.handle.S.A._fire('up');

  assert.equal(changes.length, 1);
  assert.deepEqual(changes[0].value, { x: 3, y: 4 });
  assert.equal(commits.length, 1);
  assert.equal(commits[0].name, 'A');
});

test('dispatches animageo:ready (deferred)', async () => {
  const el = new AnimageoBoard();
  el.engine = mockEngine();
  el.isConnected = true;
  const ready = new Promise((res) => el.addEventListener('animageo:ready', (e) => res(e.detail)));
  el.spec = sampleSpec();
  const detail = await ready;
  assert.ok(detail.state);
});

test('emits animageo:error for invalid inline spec', async () => {
  const el = new AnimageoBoard();
  el.engine = mockEngine();
  el.isConnected = true;
  const err = new Promise((res) => el.addEventListener('animageo:error', (e) => res(e.detail)));
  el._loadFromAttr('{ not valid json');
  const detail = await err;
  assert.match(detail.message, /invalid inline spec/);
});

test('tears down on disconnect', () => {
  const el = connected();
  assert.ok(el.handle);
  el.disconnectedCallback();
  assert.equal(el.handle, null);
});

test('inputs() exposes the schema', () => {
  const el = connected();
  const names = el.inputs().map((i) => i.name);
  assert.deepEqual(names.sort(), ['A', 'k']);
});
