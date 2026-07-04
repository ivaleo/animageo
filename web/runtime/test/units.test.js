import test from 'node:test';
import assert from 'node:assert/strict';

import { createEmitter } from '../src/emitter.js';
import { resolveParent, makeFn } from '../src/parents.js';
import { readState, applyState, initialState } from '../src/state.js';

test('emitter: on/emit/off and once', () => {
  const e = createEmitter();
  let n = 0;
  const off = e.on('change', () => (n += 1));
  e.emit('change');
  e.emit('change');
  assert.equal(n, 2);
  off();
  e.emit('change');
  assert.equal(n, 2);

  let m = 0;
  e.once('commit', () => (m += 1));
  e.emit('commit');
  e.emit('commit');
  assert.equal(m, 1);
});

test('emitter: a throwing handler is re-emitted as error', () => {
  const e = createEmitter();
  let errMsg = null;
  e.on('error', (p) => (errMsg = p.message));
  e.on('change', () => {
    throw new Error('boom');
  });
  e.emit('change');
  assert.equal(errMsg, 'boom');
});

test('resolveParent: literals, refs, arrays, fn', () => {
  const S = { A: { tag: 'A' } };
  assert.equal(resolveParent(3, S), 3);
  assert.equal(resolveParent('lbl', S), 'lbl');
  assert.deepEqual(resolveParent([1, 2], S), [1, 2]);
  assert.equal(resolveParent({ ref: 'A' }, S), S.A);
  // null in an array is a poly break → NaN
  const arr = resolveParent([1, null, 3], S);
  assert.equal(arr[0], 1);
  assert.ok(Number.isNaN(arr[1]));
  assert.equal(arr[2], 3);
});

test('resolveParent: unknown ref throws', () => {
  assert.throws(() => resolveParent({ ref: 'ZZ' }, {}), /not built/);
});

test('makeFn: closes over S', () => {
  const S = { k: { Value: () => 7 } };
  const f = makeFn('function(){return S["k"].Value();}', S);
  assert.equal(typeof f, 'function');
  assert.equal(f(), 7);
});

test('state: read/apply/initial round-trip', () => {
  const inputs = [
    { name: 'A', kind: 'point', x: -2, y: -1 },
    { name: 'k', kind: 'number', value: 3 },
    { name: 'b', kind: 'boolean', value: true },
  ];
  const S = {
    A: { _x: -2, _y: -1, X() { return this._x; }, Y() { return this._y; },
         setPosition(_m, [x, y]) { this._x = x; this._y = y; } },
    k: { _v: 3, Value() { return this._v; }, setValue(v) { this._v = v; } },
    b: { _v: true, Value() { return this._v; }, setValue(v) { this._v = v; } },
  };
  const engine = { COORDS_BY_USER: 1 };
  let updated = 0;
  const board = { update: () => (updated += 1) };

  assert.deepEqual(readState(inputs, S), { A: { x: -2, y: -1 }, k: 3, b: true });

  applyState(inputs, S, { A: { x: 4, y: 5 }, k: 9, b: false }, board, engine);
  assert.deepEqual(readState(inputs, S), { A: { x: 4, y: 5 }, k: 9, b: false });
  assert.equal(updated, 1);

  assert.deepEqual(initialState(inputs), { A: { x: -2, y: -1 }, k: 3, b: true });
});
