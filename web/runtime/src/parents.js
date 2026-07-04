/**
 * Resolve structured spec parents into the values JSXGraph's `board.create`
 * expects.
 *
 * Forms (see animageo-board/v1): `{"ref": name}` (an already-built element),
 * a number / boolean / string literal, an array (coordinate pair or sampled
 * polyline — a `null` is a poly break → NaN), `{"fn": body}` (a live
 * function-valued parent) or `{"js": expr}` (a contained escape hatch).
 *
 * The bulk of a board is fully declarative; only `fn` / `js` / `stmt` use
 * `new Function`, so a board with none of those works under a strict CSP.
 */
export function resolveParent(p, S, board) {
  if (p === null) return NaN;
  const t = typeof p;
  if (t === 'number' || t === 'boolean' || t === 'string') return p;
  if (Array.isArray(p)) return p.map((v) => (v === null ? NaN : v));
  if (t === 'object') {
    if ('ref' in p) {
      if (!(p.ref in S)) throw new Error(`parent ref "${p.ref}" not built yet`);
      return S[p.ref];
    }
    if ('fn' in p) return makeFn(p.fn, S);
    if ('js' in p) return evalExpr(p.js, S, board);
  }
  throw new Error('unknown parent form: ' + JSON.stringify(p));
}

/** A live function-valued parent, e.g. `function(){return S["k"].Value();}`. */
export function makeFn(body, S) {
  // eslint-disable-next-line no-new-func
  return new Function('S', `return (${body});`)(S);
}

/** Evaluate a contained JS expression (escape hatch) with S and board in scope. */
export function evalExpr(expr, S, board) {
  // eslint-disable-next-line no-new-func
  return new Function('S', 'board', `return (${expr});`)(S, board);
}

/** Execute a verbatim JS statement (form="stmt") with S and board in scope. */
export function runStmt(stmt, S, board) {
  // eslint-disable-next-line no-new-func
  new Function('S', 'board', stmt)(S, board);
}
