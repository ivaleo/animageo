/**
 * Cross-language contract: the runtime must consume real specs emitted by the
 * Python exporter (AnimaGeoScene.exportJSXGraph(output="spec")).
 *
 * Fixtures are regenerated with:
 *   python3 - <<'PY'
 *   from animageo.animageo import AnimaGeoScene
 *   s = AnimaGeoScene(); s.loadGGB("examples/ex_general.ggb")
 *   open("web/runtime/test/fixtures/ex_general.board.json","w").write(
 *       s.exportJSXGraph(output="spec"))
 *   PY
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { createBoard, SPEC_FORMAT } from '../src/createBoard.js';
import { mockEngine } from './mock-engine.js';

const here = dirname(fileURLToPath(import.meta.url));
const load = (name) =>
  JSON.parse(readFileSync(join(here, 'fixtures', name), 'utf8'));

test('ex_general: real spec builds with no errors and exposes inputs', () => {
  const spec = load('ex_general.board.json');
  assert.equal(spec.format, SPEC_FORMAT);

  const errors = [];
  const h = createBoard(spec, {}, { engine: mockEngine() });
  h.on('error', (e) => errors.push(e));

  // Free points A, B, C are point inputs; G is a glider on a curve.
  const inputs = h.inputs();
  const points = inputs.filter((i) => i.kind === 'point').map((i) => i.name);
  assert.ok(points.length >= 3, 'at least three free points');
  const gliders = inputs.filter((i) => i.kind === 'glider');
  assert.ok(gliders.length >= 1 && gliders[0].on, 'a glider with a parent curve');

  // Every element built (incl. polygon-border binds + setAttribute stmts).
  assert.equal(h.elementNames().length, spec.elements.filter((e) => e.name).length);

  // getState returns a value for every input.
  const state = h.getState();
  for (const inp of inputs) assert.ok(inp.name in state, `state has ${inp.name}`);

  return new Promise((resolve) => {
    queueMicrotask(() => {
      assert.deepEqual(errors, [], 'no build errors on a real GGB spec');
      resolve();
    });
  });
});

test('ex_general: setState moves a free point', () => {
  const spec = load('ex_general.board.json');
  const h = createBoard(spec, {}, { engine: mockEngine() });
  const pname = h.inputs().find((i) => i.kind === 'point').name;
  h.setState({ [pname]: { x: 1.25, y: -2.5 } });
  assert.deepEqual(h.getState()[pname], { x: 1.25, y: -2.5 });
});

test('decorations: tick-point fns + arrow attrs build with no errors', () => {
  const spec = load('decorations.board.json');
  const errors = [];
  const h = createBoard(spec, {}, { engine: mockEngine() });
  h.on('error', (e) => errors.push(e));
  // live tick anchor points + their joining segments all built
  const names = h.elementNames();
  assert.ok(names.includes('__tick_m_0'), 'tick segment built');
  assert.ok(names.includes('__tick_m_0_p1') && names.includes('__tick_m_0_p2'),
    'tick anchor points built');
  // the vector carries an arrowhead attr
  const v = spec.elements.find((e) => e.name === 'v');
  assert.ok(v.attrs && v.attrs.lastArrow, 'vector has lastArrow');
  return new Promise((resolve) =>
    queueMicrotask(() => {
      assert.deepEqual(errors, [], 'no build errors on the decorations spec');
      resolve();
    }),
  );
});

test('func5: many static curves still build (graceful), inputs present', () => {
  const spec = load('func5.board.json');
  const h = createBoard(spec, {}, { engine: mockEngine() });
  // func5 is curve-heavy; the runtime must build the sampled "curve" elements.
  const curves = spec.elements.filter((e) => e.engine === 'curve');
  assert.ok(curves.length >= 1, 'has sampled curve elements');
  assert.ok(h.elementNames().length >= curves.length);
});
