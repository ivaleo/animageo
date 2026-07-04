import test from 'node:test';
import assert from 'node:assert/strict';

import { createBoard, SPEC_FORMAT } from '../src/createBoard.js';
import { mockEngine, sampleSpec } from './mock-engine.js';

const opts = () => ({ engine: mockEngine() });

test('SPEC_FORMAT is animageo-board/v1', () => {
  assert.equal(SPEC_FORMAT, 'animageo-board/v1');
});

test('rejects a missing/unknown spec format', () => {
  assert.throws(() => createBoard(null, {}, opts()), /spec object/);
  assert.throws(
    () => createBoard({ format: 'nope', elements: [] }, {}, opts()),
    /unsupported spec format/,
  );
});

test('requires an engine', () => {
  assert.throws(() => createBoard(sampleSpec(), {}, {}), /JSXGraph .* not found/);
});

test('builds every element in order', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  assert.deepEqual(h.elementNames().sort(), ['A', 'B', 'M', 'c', 'k'].sort());
});

test('getState reads only the interactive inputs', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  assert.deepEqual(h.getState(), { A: { x: -2, y: -1 }, k: 3 });
});

test('setState / setValue mutate live objects and recompute', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  h.setState({ A: { x: 1, y: 2 } });
  assert.deepEqual(h.getState().A, { x: 1, y: 2 });
  h.setValue('k', 7);
  assert.equal(h.getState().k, 7);
  assert.ok(h.board.updates >= 2, 'board.update called on each apply');
});

test('reset returns to initial state', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  h.setState({ A: { x: 9, y: 9 }, k: 1 });
  h.reset();
  assert.deepEqual(h.getState(), { A: { x: -2, y: -1 }, k: 3 });
});

test('a live function-valued parent is wired to its input', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  const radius = h.S.c.parents[1];
  assert.equal(typeof radius, 'function');
  assert.equal(radius(), 3); // = k.Value()
  h.setValue('k', 8);
  assert.equal(radius(), 8); // tracks the slider live
});

test('change fires on drag (continuous), commit on up', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  const changes = [];
  const commits = [];
  h.on('change', (p) => changes.push(p));
  h.on('commit', (p) => commits.push(p));

  h.S.A._x = 4; // simulate the engine moving the point
  h.S.A._y = 5;
  h.S.A._fire('drag');
  h.S.A._fire('up');

  assert.equal(changes.length, 1);
  assert.equal(changes[0].name, 'A');
  assert.equal(changes[0].kind, 'point');
  assert.deepEqual(changes[0].value, { x: 4, y: 5 });
  assert.deepEqual(changes[0].state.A, { x: 4, y: 5 });

  assert.equal(commits.length, 1);
  assert.equal(commits[0].name, 'A');
});

test('debounced change collapses rapid drags', async () => {
  const h = createBoard(sampleSpec(), {}, { engine: mockEngine(), debounceMs: 10 });
  let n = 0;
  h.on('change', () => (n += 1));
  h.S.A._fire('drag');
  h.S.A._fire('drag');
  h.S.A._fire('drag');
  assert.equal(n, 0, 'nothing yet (debounced)');
  await new Promise((r) => setTimeout(r, 20));
  assert.equal(n, 1, 'collapsed to one change');
});

test('ready fires (deferred) after construction', async () => {
  const h = createBoard(sampleSpec(), {}, opts());
  const payload = await new Promise((resolve) => h.once('ready', resolve));
  assert.ok(payload.state);
  assert.deepEqual(payload.errors, []);
});

test('a bad parent ref is collected and surfaced as error, not thrown', async () => {
  const spec = sampleSpec();
  spec.elements.push({
    name: 'X',
    role: 'live',
    kind: 'midpoint',
    engine: 'midpoint',
    parents: [{ ref: 'A' }, { ref: 'NOPE' }],
    attrs: {},
  });
  const h = createBoard(spec, {}, opts());
  const err = await new Promise((resolve) => h.once('error', resolve));
  assert.equal(err.name, 'X');
  assert.match(err.message, /not built/);
  // the rest of the board still built
  assert.ok(h.elementNames().includes('M'));
});

test('getElement returns a read-only snapshot', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  const a = h.getElement('A');
  assert.equal(a.kind, 'point');
  assert.deepEqual(a.coords, { x: -2, y: -1 });
  assert.equal(h.getElement('does-not-exist'), null);
});

test('setVisible / setStyle reach the live object', () => {
  const h = createBoard(sampleSpec(), {}, opts());
  h.setVisible('M', false);
  assert.equal(h.S.M.visProp.visible, false);
  h.setStyle('M', { strokeColor: '#f00' });
  assert.equal(h.S.M.attrs.strokeColor, '#f00');
});
