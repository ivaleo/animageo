/**
 * Svelte action (template) — not part of the library core.
 *
 *   <div use:animageoBoard={{ spec, onCommit: (e) => save(e) }}
 *        style="width:640px;height:480px"></div>
 *
 *   import { animageoBoard } from './animageoBoard.js';
 *
 * Requires `@animageo/runtime` and a JSXGraph global (or pass `engine`).
 */
import { createBoard } from '@animageo/runtime';

export function animageoBoard(node, params) {
  let handle = null;

  function build(p) {
    teardown();
    if (!p || !p.spec) return;
    handle = createBoard(p.spec, node, { engine: p.engine, debounceMs: p.debounceMs });
    handle.on('ready', (e) => p.onReady?.(e));
    handle.on('change', (e) => p.onChange?.(e));
    handle.on('commit', (e) => p.onCommit?.(e));
  }

  function teardown() {
    if (handle) {
      handle.destroy();
      handle = null;
    }
  }

  build(params);
  return {
    update: build, // re-runs when params change
    destroy: teardown,
  };
}
