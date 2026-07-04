# AnimaGeo on the web — controllable movable figures

This folder is the **framework-agnostic** web integration layer for AnimaGeo
interactive geometry. It lets any web project embed *controllable* movable
figures — a construction the user can drag, exposed through a clear
signals/actions vocabulary in **construction terms** (element names + AnimaGeo
kinds), not rendering-engine terms.

See `docs/archive/jsxgraph_web_integration_audit.md` and
`docs/archive/jsxgraph_web_integration_plan.md` for the design.

## Pipeline

```
Python (the library)
  AnimaGeoScene.exportJSXGraph(output="spec")  →  animageo-board/v1  (pure data)
                                                  (board.schema.json)
JavaScript (this folder)
  @animageo/runtime         createBoard(spec, container, opts) -> BoardHandle
                            signals: ready/change/commit/viewchange/error
                            actions: getState/setState/setValue/reset/...
  @animageo/web-component   <animageo-board>  (CustomEvents + methods + property)
  adapters/                 React / Vue / Svelte / vanilla — thin templates
```

The library (Python) owns the **contract** (the spec + its JSON schema) and the
**runtime + web component** (engine-neutral, no framework). Each consuming
project writes its own ~30-line adapter for its stack — examples in `adapters/`.

## Packages

| Path | What |
|------|------|
| [`runtime/`](runtime) | `@animageo/runtime` — headless board + signals/actions handle. JSXGraph is injected/peer. |
| [`web-component/`](web-component) | `@animageo/web-component` — `<animageo-board>`, the zero-framework primitive. |
| [`adapters/`](adapters) | React hook / Vue composable / Svelte action / vanilla — copy-paste templates. |

## Try it

```bash
# 1) produce a spec from a construction
python -m animageo examples/scene.ggb -o board.html   # quick self-contained page
# or, for the data contract:
python - <<'PY'
from animageo.animageo import AnimaGeoScene
s = AnimaGeoScene(); s.loadGGB("examples/ex_general.ggb")
open("web/runtime/test/fixtures/ex_general.board.json","w").write(s.exportJSXGraph(output="spec"))
PY

# 2) serve and open a demo
cd web && python3 -m http.server 8000
#   → http://localhost:8000/web-component/demo.html
#   → http://localhost:8000/adapters/vanilla.html

# 3) run the JS tests (no extra deps)
cd web/runtime && node --test
cd web/web-component && node --test

# 4) real-browser smoke against live JSXGraph (skips if no Chrome)
node web/runtime/scripts/browser-smoke/run.mjs
```

## Status

Phase 1 (spec contract) and Phase 2 (runtime) are done and tested; Phase 3 (web
component + adapters) is in place. Phase 4 (visual parity: label placement, dash
patterns, angle multi-arc, z-order; static-curve resampling on pan/zoom) is the
next track — see the plan doc.
