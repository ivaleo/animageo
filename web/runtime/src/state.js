/**
 * Canonical board state ↔ live JSXGraph objects.
 *
 * State is keyed by input name and self-describing per kind:
 *   point / glider / text → { x, y }
 *   number / angle → number
 *   boolean        → boolean
 *
 * This is the same value family the keyframe system uses, so animations and
 * the live widget share one vocabulary.
 */
export function readState(inputs, S) {
  const state = {};
  for (const inp of inputs) {
    const obj = S[inp.name];
    if (!obj) continue;
    state[inp.name] = readInput(inp, obj);
  }
  return state;
}

export function readInput(inp, obj) {
  switch (inp.kind) {
    case 'point':
    case 'glider':
    case 'text':
      return { x: num(obj.X()), y: num(obj.Y()) };
    case 'number':
    case 'angle':
      return num(obj.Value());
    case 'boolean':
      return !!obj.Value();
    default:
      return null;
  }
}

/** Push a partial state into the board, then recompute. */
export function applyState(inputs, S, partial, board, engine) {
  const byName = new Map(inputs.map((i) => [i.name, i]));
  for (const name of Object.keys(partial)) {
    const inp = byName.get(name);
    const obj = S[name];
    if (!inp || !obj) continue;
    applyInput(inp, obj, partial[name], engine);
  }
  if (board && typeof board.update === 'function') board.update();
}

function applyInput(inp, obj, value, engine) {
  switch (inp.kind) {
    case 'point':
    case 'glider':
    case 'text': {
      const x = value && typeof value === 'object' ? value.x : undefined;
      const y = value && typeof value === 'object' ? value.y : undefined;
      if (x != null && y != null && typeof obj.setPosition === 'function') {
        obj.setPosition(engine.COORDS_BY_USER, [x, y]);
      }
      break;
    }
    case 'number':
    case 'angle':
      if (typeof obj.setValue === 'function') obj.setValue(Number(value));
      break;
    case 'boolean':
      if (typeof obj.setValue === 'function') obj.setValue(!!value);
      break;
    default:
      break;
  }
}

/** Initial state from the input schema (for `reset()`). */
export function initialState(inputs) {
  const st = {};
  for (const i of inputs) {
    if (i.kind === 'point' || i.kind === 'glider' || i.kind === 'text') st[i.name] = { x: i.x, y: i.y };
    else st[i.name] = i.value;
  }
  return st;
}

function num(v) {
  return typeof v === 'number' ? v : Number(v);
}
