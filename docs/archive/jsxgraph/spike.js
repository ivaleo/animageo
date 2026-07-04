/* AnimaGeo — JSXGraph export Phase 0 spike (hand-written reference target).
 *
 * Reproduces a small AnimaGeo construction as a *live* JSXGraph board to
 * de-risk the architecture before building the generic pipeline:
 *
 *   A, B          free points          -> 'point'   (draggable)
 *   M = Midpoint  derived point        -> 'midpoint' (live)
 *   seg = Segment derived segment      -> 'segment'  (live)
 *   c = Circle    derived circle (A,B) -> 'circle'   (live)
 *   P            point on c            -> 'glider'   (draggable along c)
 *   r            free number           -> 'slider'
 *   k = Circle    M, radius = r        -> 'circle' with function radius (live)
 *
 * This is the structure the Phase 1 `output="html"` pipeline must generate
 * automatically from the construction graph (see docs/jsxgraph_export_plan.md).
 */
(function () {
  // boundingbox is [left, top, right, bottom] in math units (MU) — from
  // AnimaGeoScene._get_scene_bounds in the real pipeline.
  const board = JXG.JSXGraph.initBoard('agbox', {
    boundingbox: [-6, 5, 6, -5],
    keepaspectratio: true,
    axis: true,
    showNavigation: true,
    showCopyright: false,
    pan: { enabled: true },
    zoom: { enabled: true },
  });

  // LaTeX labels: AnimaGeo's resolve_label_text() output feeds these.
  // The label text uses MathJax (board option set in the HTML scaffold).
  const LBL = { label: { useMathJax: true } };

  // ── independents (the interactive inputs) ──────────────────────────────
  // free_point -> draggable point
  const A = board.create('point', [-2, -1],
    Object.assign({ name: '$A$', size: 3, strokeColor: '#c0392b', fillColor: '#c0392b' }, LBL));
  const B = board.create('point', [2, 1],
    Object.assign({ name: '$B$', size: 3, strokeColor: '#c0392b', fillColor: '#c0392b' }, LBL));

  // number -> slider (range [0, 5], start 3): [[x1,y1],[x2,y2],[min,start,max]]
  const r = board.create('slider', [[-5, 4], [-1.5, 4], [0, 3, 5]],
    Object.assign({ name: '$r$' }, LBL));

  // ── derived elements (live; recompute when A/B/r move) ─────────────────
  const M = board.create('midpoint', [A, B],
    Object.assign({ name: '$M$', size: 2, strokeColor: '#2c3e50', fillColor: '#2c3e50' }, LBL));

  const seg = board.create('segment', [A, B],
    { strokeColor: '#2c3e50', strokeWidth: 2 });

  // Circle through B centred at A  (AnimaGeo: Circle(A, B))
  const c = board.create('circle', [A, B],
    { strokeColor: '#2980b9', strokeWidth: 2, fillColor: '#2980b9', fillOpacity: 0.06 });

  // tparam_point on a circle -> glider, seeded with current coords.
  const P = board.create('glider', [2.4, -0.2, c],
    Object.assign({ name: '$P$', size: 3, strokeColor: '#27ae60', fillColor: '#27ae60' }, LBL));

  // Circle centred at M with a function-valued radius driven by the slider.
  // (Demonstrates Tier-V "live value": radius = r.Value().)
  const k = board.create('circle', [M, function () { return r.Value(); }],
    { strokeColor: '#8e44ad', strokeWidth: 1.5, dash: 2 });

  // A MathJax text to confirm LaTeX rendering inside the scaffold.
  board.create('text', [-5.6, -4.4, '\\(M=\\dfrac{A+B}{2},\\quad P\\in c\\)'],
    { useMathJax: true, fontSize: 16, anchorX: 'left' });

  // Expose for manual inspection in the browser console.
  window.agboard = board;
})();
