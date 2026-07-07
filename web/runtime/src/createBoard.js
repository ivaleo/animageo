/**
 * createBoard — the headless, framework-agnostic entry point.
 *
 *   const handle = createBoard(spec, container, opts);
 *   handle.on('change', ({ name, value, state }) => …);
 *   handle.setState({ A: { x: 1, y: 2 } });
 *
 * `spec`      — an animageo-board/v1 object (AnimaGeo exportJSXGraph(output="spec")).
 * `container` — a DOM element or its id.
 * `opts`      — { engine?, debounceMs?, showNavigation?, pan?, zoom?, mathjax? }.
 *               `engine` defaults to `globalThis.JXG` (the JSXGraph global).
 *
 * The returned handle exposes construction-relative signals (out) and actions
 * (in); the vocabulary is element names + AnimaGeo kinds, never JSXGraph
 * internals.
 */
import { createEmitter } from './emitter.js';
import { buildBoard } from './driver.js';
import { applyState, initialState, readState } from './state.js';

export const SPEC_FORMAT = 'animageo-board/v1';

export function createBoard(spec, container, opts = {}) {
  if (!spec || typeof spec !== 'object') {
    throw new Error('createBoard: a spec object is required');
  }
  if (spec.format !== SPEC_FORMAT) {
    throw new Error(
      `createBoard: unsupported spec format ${JSON.stringify(spec.format)} ` +
        `(expected ${SPEC_FORMAT})`,
    );
  }
  const engine =
    opts.engine || (typeof globalThis !== 'undefined' ? globalThis.JXG : undefined);
  if (!engine || !engine.JSXGraph) {
    throw new Error('createBoard: JSXGraph (JXG) not found — load it or pass opts.engine');
  }

  const inputs = spec.inputs || [];
  const inputByName = new Map(inputs.map((i) => [i.name, i]));
  const emitter = createEmitter();
  const debounceMs = opts.debounceMs != null ? opts.debounceMs : 0;

  const { board, S, errors } = buildBoard(spec, container, engine, opts);

  // ── signals: change (continuous) + commit (drag end) per interactive input ──
  let changeTimer = null;
  function fireChange(name) {
    const run = () => {
      const state = readState(inputs, S);
      emitter.emit('change', {
        name,
        kind: inputByName.get(name) && inputByName.get(name).kind,
        value: state[name],
        state,
      });
    };
    if (debounceMs > 0) {
      clearTimeout(changeTimer);
      changeTimer = setTimeout(run, debounceMs);
    } else {
      run();
    }
  }
  function fireCommit(name) {
    const state = readState(inputs, S);
    emitter.emit('commit', {
      name,
      kind: inputByName.get(name) && inputByName.get(name).kind,
      value: state[name],
      state,
    });
  }
  for (const inp of inputs) {
    const obj = S[inp.name];
    if (!obj || typeof obj.on !== 'function') continue;
    obj.on('drag', () => fireChange(inp.name));
    obj.on('up', () => fireCommit(inp.name));
  }
  if (typeof board.on === 'function') {
    board.on('boundingbox', () =>
      emitter.emit('viewchange', { boundingbox: getBBox(board) }),
    );
  }

  // ── actions ──────────────────────────────────────────────────────────────
  const handle = {
    board,
    S,
    on: emitter.on,
    once: emitter.once,
    getState: () => readState(inputs, S),
    setState: (partial) => applyState(inputs, S, partial || {}, board, engine),
    getValue: (name) => readState(inputs, S)[name],
    setValue: (name, value) =>
      applyState(inputs, S, { [name]: value }, board, engine),
    getElement: (name) => {
      const o = S[name];
      if (!o) return null;
      const inp = inputByName.get(name);
      const out = { name, kind: inp ? inp.kind : null };
      if (typeof o.X === 'function' && typeof o.Y === 'function') {
        out.coords = { x: o.X(), y: o.Y() };
      }
      if (typeof o.Value === 'function') out.value = o.Value();
      if (o.visProp) out.visible = o.visProp.visible !== false;
      return out;
    },
    reset: () => applyState(inputs, S, initialState(inputs), board, engine),
    setVisible: (name, on) => {
      const o = S[name];
      if (o && typeof o.setAttribute === 'function') {
        o.setAttribute({ visible: !!on });
        board.update && board.update();
      }
    },
    setStyle: (name, attrs) => {
      const o = S[name];
      if (o && typeof o.setAttribute === 'function') {
        const next = { ...(attrs || {}) };
        const labelAttrs = next.label;
        if (labelAttrs && o.label && typeof o.label.setAttribute === 'function') {
          o.label.setAttribute(labelAttrs);
          delete next.label;
        }
        if (Object.keys(next).length) o.setAttribute(next);
        board.update && board.update();
      }
    },
    setBoundingBox: (bbox) => {
      if (typeof board.setBoundingBox === 'function') board.setBoundingBox(bbox, false);
    },
    fitView: () => {
      if (typeof board.setBoundingBox === 'function') {
        board.setBoundingBox(spec.boundingbox, false);
      }
    },
    resize: () => {
      if (typeof board.resizeContainer === 'function' && container && container.clientWidth) {
        board.resizeContainer(container.clientWidth, container.clientHeight);
        board.update && board.update();
      }
    },
    inputs: () => inputs.map((i) => ({ ...i })),
    elementNames: () => Object.keys(S),
    coverage: () => (spec.coverage || []).map((c) => ({ ...c })),
    toSVG: () => svgOf(container),
    destroy: () => {
      emitter.clear();
      try {
        engine.JSXGraph.freeBoard(board);
      } catch {
        /* ignore */
      }
    },
  };

  // ── ready + surface build errors (deferred so sync subscribers catch them) ──
  scheduleReady(emitter, opts, () => ({ state: readState(inputs, S), errors }));
  for (const e of errors) queueMicro(() => emitter.emit('error', e));

  return handle;
}

function getBBox(board) {
  try {
    return typeof board.getBoundingBox === 'function' ? board.getBoundingBox() : undefined;
  } catch {
    return undefined;
  }
}

function svgOf(container) {
  const node =
    container && typeof container.querySelector === 'function'
      ? container.querySelector('svg')
      : null;
  return node ? node.outerHTML : '';
}

function queueMicro(fn) {
  if (typeof queueMicrotask === 'function') queueMicrotask(fn);
  else Promise.resolve().then(fn);
}

function scheduleReady(emitter, opts, payloadFn) {
  const fire = () => emitter.emit('ready', payloadFn());
  const MJ = typeof globalThis !== 'undefined' ? globalThis.MathJax : undefined;
  if (opts.mathjax !== false && MJ && typeof MJ.typesetPromise === 'function') {
    MJ.typesetPromise().then(fire, fire);
  } else {
    queueMicro(fire);
  }
}
