import test from 'node:test';
import assert from 'node:assert/strict';
import { createBoard } from '../src/index.js';
import { sampleSpec } from './mock-engine.js';

import { domEngine } from './paint-engine.js';

test('exported part order moves actual render nodes once and survives local input changes', () => {
  const spec = sampleSpec();
  spec.paintOrder = { mode: 'area', static: true, fillOrder: ['c'], partOrder: [
    { id: 'A', part: 'label', targets: [{ name: 'A', node: 'label' }] },
    { id: 'c', part: 'fill', targets: [{ name: 'c', node: 'self' }] },
    { id: 'B', part: 'body', targets: [{ name: 'B', node: 'self' }] },
  ] };
  const h = createBoard(spec, {}, { engine: domEngine() });
  const wanted = [h.S.A.label.rendNode, h.S.c.rendNode, h.S.B.rendNode];
  assert.deepEqual(h.board.nodes.slice(-3), wanted);
  const before = [...h.board.nodes];
  h.setValue('A', { x: 20, y: 30 });
  h.S.A._fire('drag');
  h.board._fire('update');
  assert.deepEqual(h.board.nodes, before);
});

test('Python board order consumes the portable paint fixture without sorting it', async () => {
  const { readFile } = await import('node:fs/promises');
  const spec = JSON.parse(await readFile(new URL('./fixtures/fill_order.board.json', import.meta.url)));
  const paint = JSON.parse(await readFile(new URL('../../../animageo/native/parity/v1/paint/paint_fill_order.json', import.meta.url)));
  const oracle = paint.cases.find((c) => c.name === 'nested_circle_and_polygon').expect;
  assert.deepEqual(spec.paintOrder.fillOrder, oracle.fillOrder);
  assert.deepEqual(spec.paintOrder.partOrder.map(({ id, part }) => ({ id, part })), oracle.partOrder);
  const h = createBoard(spec, {}, { engine: domEngine() });
  const expected = spec.paintOrder.partOrder.flatMap((ref) => ref.targets.flatMap((t) => {
    const obj = h.S[t.name];
    return t.node === 'borders' ? (obj.borders || []).map((o) => o.rendNode).filter(Boolean)
      : [t.node === 'label' ? obj.label?.rendNode : obj.rendNode].filter(Boolean);
  }));
  assert.deepEqual(h.board.nodes.slice(-expected.length), expected);
  const before = [...h.board.nodes];
  h.setValue('R', { x: .1, y: 0 });
  h.S.R._fire('drag');
  h.board.update();
  assert.deepEqual(h.board.nodes, before);
});

test('all portable fill-order cases can be consumed as ready display lists', async () => {
  const { readFile } = await import('node:fs/promises');
  const { applyPaintOrder } = await import('../src/paintOrder.js');
  const paint = JSON.parse(await readFile(new URL('../../../animageo/native/parity/v1/paint/paint_fill_order.json', import.meta.url)));
  for (const { name, expect } of paint.cases) {
    const nodes = [];
    const layer = { appendChild(node) { const i=nodes.indexOf(node); if(i>=0) nodes.splice(i,1); nodes.push(node); } };
    const S = Object.create(null);
    const partOrder = expect.partOrder.map(({ id, part }, i) => {
      const target = 'part'+i;
      S[target] = { rendNode: { id, part } };
      return { id, part, targets: [{ name: target, node: 'self' }] };
    });
    applyPaintOrder({ renderer: { layer: { 9: layer } } }, S, { partOrder });
    assert.deepEqual(nodes, expect.partOrder, name);
    assert.deepEqual(nodes.filter((n)=>n.part==='fill').map((n)=>n.id), expect.fillOrder, name);
  }
});

async function smokeBoard(t, spec) {
  const { runSmoke } = await import('../scripts/browser-smoke/smoke-runner.js');
  const engine = domEngine();
  const init = engine.JSXGraph.initBoard;
  engine.JSXGraph.initBoard = (...args) => {
    const board = init(...args);
    board.renderer.layer[9].childNodes = board.nodes;
    board.setBoundingBox = () => board._fire('boundingbox');
    const create = board.create;
    board.create = (type, parents, attrs) => {
      const obj = create(type, parents, attrs);
      obj.triggerEventHandlers = (events) => events.forEach((ev) => obj._fire(ev));
      if (type === 'circle') obj.Radius = () => typeof parents[1] === 'number' ? parents[1]
        : Math.hypot(parents[1].X() - parents[0].X(), parents[1].Y() - parents[0].Y());
      return obj;
    };
    return board;
  };
  const previous = { window: globalThis.window, document: globalThis.document };
  globalThis.window = { JXG: engine, addEventListener() {} };
  globalThis.document = { getElementById: () => ({ querySelector: () => ({ outerHTML: '<svg></svg>' }) }) };
  t.after(() => {
    for (const key of ['window', 'document']) {
      if (previous[key] === undefined) delete globalThis[key];
      else globalThis[key] = previous[key];
    }
  });
  return runSmoke(spec);
}

const paintChecks = [
  'exported part targets exist',
  'initial DOM matches export-frame part order',
  'exported fill rule outer',
  'exported fill rule inner',
];
const dragChecks = [
  'drag reverses live circle area',
  'drag preserves export-frame DOM order',
  'reset preserves export-frame DOM order',
];

test('smoke executes paint checks without a point input', async (t) => {
  const { readFile } = await import('node:fs/promises');
  const spec = JSON.parse(await readFile(new URL('./fixtures/fill_order.board.json', import.meta.url)));
  spec.inputs = [];
  const result = await smokeBoard(t, spec);
  for (const name of paintChecks) assert.equal(result.checks.find((c) => c.name === name)?.pass, true, name);
  assert.equal(result.checks.some((c) => dragChecks.includes(c.name)), false);
});

test('smoke executes initial order and drag checks on the exported free radius input', async (t) => {
  const { readFile } = await import('node:fs/promises');
  const spec = JSON.parse(await readFile(new URL('./fixtures/fill_order.board.json', import.meta.url)));
  assert.ok(spec.inputs.some((i) => i.name === 'R' && i.kind === 'point'));
  const result = await smokeBoard(t, spec);
  for (const name of ['ready fired', 'has a point input', ...paintChecks, ...dragChecks]) {
    assert.equal(result.checks.find((c) => c.name === name)?.pass, true, name);
  }
  assert.equal(result.ok, true, JSON.stringify(result));
});
