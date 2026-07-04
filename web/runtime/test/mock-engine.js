/**
 * A tiny fake JSXGraph engine for tests — implements just enough of the API the
 * runtime touches (create / on / update / X / Y / Value / setValue /
 * setPosition / setAttribute), plus a `_fire(event)` hook to simulate user
 * interaction (drag/up). No DOM, no real geometry.
 */
export function mockEngine() {
  function makeObj(type, parents, attrs) {
    const handlers = {};
    const o = {
      type,
      parents,
      attrs: { ...(attrs || {}) },
      _x: 0,
      _y: 0,
      _val: 0,
      visProp: { visible: !(attrs && attrs.visible === false) },
      X() {
        return this._x;
      },
      Y() {
        return this._y;
      },
      Value() {
        return this._val;
      },
      setValue(v) {
        this._val = v;
      },
      setPosition(_mode, [x, y]) {
        this._x = x;
        this._y = y;
      },
      setAttribute(a) {
        Object.assign(this.attrs, a);
        if (a && 'visible' in a) this.visProp.visible = a.visible;
      },
      on(ev, cb) {
        (handlers[ev] || (handlers[ev] = [])).push(cb);
      },
      _fire(ev) {
        (handlers[ev] || []).forEach((cb) => cb());
      },
    };
    return o;
  }

  return {
    COORDS_BY_USER: 1,
    JSXGraph: {
      initBoard(_container, cfg) {
        const bhandlers = {};
        return {
          cfg,
          updates: 0,
          create(type, parents, attrs) {
            const o = makeObj(type, parents, attrs);
            if ((type === 'point' || type === 'glider') && typeof parents[0] === 'number') {
              o._x = parents[0];
              o._y = parents[1];
            }
            if (type === 'slider' && Array.isArray(parents[2])) o._val = parents[2][1];
            if (type === 'checkbox') o._val = false;
            // Polygons expose live edges; real specs bind named edges to these.
            if (type === 'polygon') {
              o.borders = parents.map(() => makeObj('line', [], {}));
            }
            return o;
          },
          on(ev, cb) {
            (bhandlers[ev] || (bhandlers[ev] = [])).push(cb);
          },
          _fire(ev) {
            (bhandlers[ev] || []).forEach((cb) => cb());
          },
          update() {
            this.updates += 1;
          },
          setBoundingBox() {},
          getBoundingBox() {
            return cfg.boundingbox;
          },
        };
      },
      freeBoard() {},
    },
  };
}

/** A representative spec: free point A, slider k, fixed point B, midpoint M,
 * circle c with a live (k-driven) radius. */
export function sampleSpec() {
  return {
    format: 'animageo-board/v1',
    boundingbox: [-5, 5, 5, -5],
    size: [400, 400],
    chrome: { axis: true, grid: false, keepAspectRatio: true },
    options: {},
    inputs: [
      { name: 'A', kind: 'point', x: -2, y: -1 },
      { name: 'k', kind: 'number', value: 3, min: 0, max: 10, step: 0.5 },
    ],
    elements: [
      { name: 'A', role: 'input', kind: 'point', engine: 'point', parents: [-2, -1], attrs: {} },
      {
        name: 'k',
        role: 'input',
        kind: 'number',
        engine: 'slider',
        parents: [[-4, 4], [-1, 4], [0, 3, 10]],
        attrs: {},
      },
      { name: 'B', role: 'static', kind: 'Point', engine: 'point', parents: [2, 1], attrs: {} },
      {
        name: 'M',
        role: 'live',
        kind: 'Point',
        engine: 'midpoint',
        parents: [{ ref: 'A' }, { ref: 'B' }],
        attrs: {},
      },
      {
        name: 'c',
        role: 'live',
        kind: 'Circle',
        engine: 'circle',
        parents: [{ ref: 'A' }, { fn: 'function(){return S["k"].Value();}' }],
        attrs: {},
      },
    ],
    coverage: [],
  };
}
