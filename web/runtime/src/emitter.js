/**
 * Minimal synchronous pub/sub for board signals.
 *
 * Signals: `ready`, `change`, `commit`, `select`, `viewchange`, `error`.
 * Handlers that throw are isolated; the failure is re-emitted as `error`
 * (except failures inside an `error` handler, to avoid a loop).
 */
export function createEmitter() {
  const map = new Map(); // signal -> Set<fn>

  function on(signal, cb) {
    let set = map.get(signal);
    if (!set) {
      set = new Set();
      map.set(signal, set);
    }
    set.add(cb);
    return () => set.delete(cb);
  }

  function once(signal, cb) {
    const off = on(signal, (payload) => {
      off();
      cb(payload);
    });
    return off;
  }

  function emit(signal, payload) {
    const set = map.get(signal);
    if (!set) return;
    for (const cb of [...set]) {
      try {
        cb(payload);
      } catch (err) {
        if (signal !== 'error') {
          emit('error', { message: String((err && err.message) || err), error: err });
        }
      }
    }
  }

  function clear() {
    map.clear();
  }

  return { on, once, emit, clear };
}
