// Vendored snapshot of @animageo/runtime for the guide's live demo.
// Source of truth: web/runtime/src/. Regenerate: cp web/runtime/src/*.js here.
/**
 * @animageo/runtime — framework-agnostic runtime for AnimaGeo interactive
 * geometry boards. Build a live JSXGraph board from an animageo-board/v1 spec
 * and drive it through a signals/actions handle.
 *
 *   import { createBoard } from '@animageo/runtime';
 *   const handle = createBoard(spec, document.getElementById('box'));
 *   handle.on('change', ({ name, value }) => console.log(name, value));
 */
export { createBoard, SPEC_FORMAT } from './createBoard.js';
export { readState, applyState, initialState } from './state.js';

export const version = '0.1.0';
