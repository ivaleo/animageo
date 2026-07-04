/**
 * JSXGraph engine driver: turn an animageo-board/v1 spec into a live board.
 *
 * The only place that knows JSXGraph specifics. The engine is injected (so the
 * Python side stays engine-neutral and the runtime is testable with a mock),
 * defaulting to `globalThis.JXG` in `createBoard`.
 */
import { evalExpr, resolveParent, runStmt } from './parents.js';

/** Build the board. Returns `{ board, S, errors }`. Per-element failures are
 * collected (not thrown) so one bad element can't blank the whole figure. */
export function buildBoard(spec, container, engine, opts = {}) {
  const [l, t, r, b] = spec.boundingbox;
  const chrome = spec.chrome || {};
  const board = engine.JSXGraph.initBoard(container, {
    boundingbox: [l, t, r, b],
    keepaspectratio: chrome.keepAspectRatio !== false,
    axis: !!chrome.axis,
    grid: !!chrome.grid,
    showNavigation: opts.showNavigation !== false,
    showCopyright: false,
    pan: { enabled: opts.pan !== false },
    zoom: { enabled: opts.zoom !== false },
  });
  applyChrome(board, chrome);

  const S = Object.create(null);
  const errors = [];
  for (const el of spec.elements || []) {
    try {
      buildElement(el, board, S);
    } catch (err) {
      errors.push({
        name: el.name || '(stmt)',
        message: String((err && err.message) || err),
        error: err,
      });
    }
  }
  return { board, S, errors };
}

function buildElement(el, board, S) {
  const form = el.form || 'create';
  if (form === 'stmt') {
    runStmt(el.js, S, board);
    return;
  }
  if (form === 'bind') {
    S[el.name] = evalExpr(el.bind, S, board);
    return;
  }
  const parents = (el.parents || []).map((p) => resolveParent(p, S, board));
  S[el.name] = board.create(el.engine, parents, el.attrs || {});
}

/** Best-effort board background. Axes/grid visibility are set at initBoard;
 * detailed axis/grid styling is a later (Phase 4) refinement. Everything is
 * guarded so the runtime degrades on engines without `containerObj`. */
function applyChrome(board, chrome) {
  try {
    if (chrome.background && board.containerObj) {
      board.containerObj.style.background = chrome.background;
    }
  } catch {
    /* ignore */
  }
}
