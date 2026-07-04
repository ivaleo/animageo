/**
 * In-page smoke logic: build a real spec with the live JSXGraph engine and
 * assert the runtime drives it correctly. Returns a plain result object.
 *
 * This is the verification the mock-based tests cannot give: it exercises the
 * real `board.create` signatures, object methods (X/Y/Value/setPosition/
 * setAttribute), event system (drag/up via triggerEventHandlers), the
 * fn/js/stmt escape hatches, and the SVG renderer.
 */
import { createBoard } from '../../src/index.js';

export async function runSmoke(spec) {
  const result = { ok: false, checks: [], errors: [] };
  const check = (name, cond, info) =>
    result.checks.push({ name, pass: !!cond, info: info || '' });

  window.addEventListener('error', (e) =>
    result.errors.push(String((e && e.message) || e)),
  );

  const box = document.getElementById('box');
  const changes = [];
  const commits = [];
  const views = [];
  let handle;
  try {
    handle = createBoard(spec, box, { engine: window.JXG });
  } catch (e) {
    result.errors.push('createBoard threw: ' + ((e && e.message) || e));
    return result;
  }
  handle.on('change', (p) => changes.push(p));
  handle.on('commit', (p) => commits.push(p));
  handle.on('viewchange', (p) => views.push(p));

  let ready = false;
  await new Promise((res) =>
    handle.once('ready', () => {
      ready = true;
      res();
    }),
  );
  check('ready fired', ready);

  const inputs = handle.inputs();
  const pt = inputs.find((i) => i.kind === 'point');
  check('has a point input', !!pt, pt && pt.name);
  if (!pt) return result;

  // getState reads real JSXGraph objects
  const s0 = handle.getState();
  check(
    'getState returns coords for point',
    s0[pt.name] && typeof s0[pt.name].x === 'number',
    JSON.stringify(s0[pt.name]),
  );

  // setState moves a real point (setPosition + COORDS_BY_USER + board.update)
  handle.setState({ [pt.name]: { x: 1.25, y: -2.5 } });
  const s1 = handle.getState();
  check(
    'setState moved the point',
    Math.abs(s1[pt.name].x - 1.25) < 1e-6 && Math.abs(s1[pt.name].y + 2.5) < 1e-6,
    JSON.stringify(s1[pt.name]),
  );

  // real event wiring: move + fire JSXGraph's own drag/up handlers
  const obj = handle.S[pt.name];
  if (obj && typeof obj.triggerEventHandlers === 'function') {
    obj.setPosition(window.JXG.COORDS_BY_USER, [2, 3]);
    obj.triggerEventHandlers(['drag'], [{}]);
    obj.triggerEventHandlers(['up'], [{}]);
    check(
      'change + commit fired via real JSXGraph events',
      changes.length >= 1 && commits.length >= 1,
      'changes=' + changes.length + ' commits=' + commits.length,
    );
    const last = changes[changes.length - 1];
    check(
      'change payload carries the new coords',
      last && Math.abs(last.value.x - 2) < 1e-6 && Math.abs(last.value.y - 3) < 1e-6,
      last && JSON.stringify(last.value),
    );
  } else {
    check('triggerEventHandlers available on real objects', false);
  }

  // a slider exists in some specs; if so, setValue must take
  const num = inputs.find((i) => i.kind === 'number' || i.kind === 'angle');
  if (num) {
    handle.setValue(num.name, 5);
    check('setValue on slider', Math.abs(handle.getState()[num.name] - 5) < 1e-6);
  }

  // viewchange fires on a real pan/zoom (board bounding-box change). Hosts use
  // this to re-request geometry for static (frozen) curves when the viewport
  // grows beyond the sampled range.
  if (typeof handle.setBoundingBox === 'function') {
    handle.setBoundingBox([-12, 9, 12, -9]);
    check('viewchange fired on setBoundingBox', views.length >= 1,
      views.length ? JSON.stringify(views[views.length - 1].boundingbox) : 'none');
  }

  // SVG actually rendered by JSXGraph
  const svg = handle.toSVG();
  check('toSVG returns rendered SVG', svg && svg.indexOf('<svg') !== -1, 'len=' + (svg ? svg.length : 0));
  check('built elements', handle.elementNames().length > 0, 'n=' + handle.elementNames().length);

  result.ok = result.errors.length === 0 && result.checks.every((c) => c.pass);
  return result;
}
