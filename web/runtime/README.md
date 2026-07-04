# @animageo/runtime

Framework-agnostic runtime for **AnimaGeo interactive geometry boards**. It
builds a live, draggable [JSXGraph](https://jsxgraph.org) board from an
`animageo-board/v1` **spec** and exposes a small **signals/actions** handle — so
any web project (React, Vue, Svelte, vanilla, no-build) can embed controllable
movable figures and react to user motion.

No framework dependency. The spec is plain data (produced by Python:
`AnimaGeoScene.exportJSXGraph(output="spec")`); this package turns it into a
board and a handle.

## Install

```bash
npm i @animageo/runtime jsxgraph
```

`jsxgraph` is a peer dependency. Load it however you like (bundler import or a
`<script>`/CDN that defines the `JXG` global).

## Use

```js
import { createBoard } from '@animageo/runtime';

const spec = await fetch('/board.json').then((r) => r.json()); // animageo-board/v1
const handle = createBoard(spec, document.getElementById('box'));

handle.on('ready',  () => console.log('built', handle.getState()));
handle.on('change', ({ name, value, state }) => updateApp(state)); // continuous (drag)
handle.on('commit', ({ name, value }) => save(name, value));       // drag end

handle.setState({ A: { x: 1, y: 2 } }); // drive it from the app
```

If `JXG` is not a global, inject it: `createBoard(spec, el, { engine: JXG })`.

## Signals (out)

| Signal | Payload | When |
|--------|---------|------|
| `ready` | `{ state, errors }` | board built (after MathJax typeset, if any) |
| `change` | `{ name, kind, value, state }` | a free point / slider / glider moves (continuous) |
| `commit` | `{ name, kind, value, state }` | the drag ends |
| `viewchange` | `{ boundingbox }` | pan / zoom |
| `error` | `{ name, message, error }` | a single element failed to build |

`name`/`kind` are construction terms (element name + AnimaGeo kind), never
JSXGraph internals. `state` is the full canonical state at that moment.

## Actions (in)

```
getState() -> State                 setState(partial)
getValue(name)                      setValue(name, value)
getElement(name) -> snapshot        reset()
setVisible(name, on)                setStyle(name, attrs)
setBoundingBox(bbox)                fitView()   resize()
inputs() -> schema[]                elementNames()   coverage()
toSVG() -> string                   destroy()
on(sig, cb) -> off                  once(sig, cb)
```

State value per input kind: `point`/`glider` → `{ x, y }`; `number`/`angle` →
number; `boolean` → boolean. (Same value family as AnimaGeo keyframes.)

## Options

`createBoard(spec, container, opts)` — `engine`, `debounceMs` (collapse rapid
`change`), `showNavigation`, `pan`, `zoom`, `mathjax`.

## Notes

- Mostly declarative: only live function-valued parents (`{"fn":…}`) and the few
  advanced constructs (`{"js":…}`, `bind`, `stmt`) use `new Function`. A spec
  with none of those runs under a strict CSP.
- One board per call; multiple boards per page are independent (no globals).
- **Static (frozen) curves** — functions, implicit curves, conics-by-equation,
  arcs, loci — are sampled by the Python exporter to the export viewport. They
  do not re-sample on pan/zoom (the analytic definition isn't shipped). On a big
  zoom-out a sampled curve can end abruptly; subscribe to `viewchange` and
  re-export a spec for the new bounding box if you need crisp curves at any
  zoom. (Live elements — points, lines, circles, conics built from points — are
  exact at any zoom.)
- `npm test` runs the suite on Node's built-in test runner (no extra deps),
  including a cross-language contract test against real Python-generated specs.
- `node scripts/browser-smoke/run.mjs` runs a **real headless-Chrome smoke**
  against live JSXGraph (build a real spec, drag a point, assert change/commit
  fire and the SVG renders). Skips cleanly if Chrome isn't installed; vendors
  JSXGraph on first run. Add `--screenshot` to also write a `screenshot.png`
  (MathJax labels typeset, like the real `html` export) for visual inspection /
  a future visual-regression baseline.
