# AnimaGeo on the web — controllable movable figures

This folder is the **framework-agnostic** web integration layer for AnimaGeo
interactive geometry. It lets any web project embed *controllable* movable
figures — a construction the user can drag, exposed through a clear
signals/actions vocabulary in **construction terms** (element names + AnimaGeo
kinds), not rendering-engine terms.

See [the export-format guide](../docs/export_formats.md#interactive-jsxgraph)
for the public Python-to-browser contract.

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

From the repository root, use the tracked sample construction:

```bash
# 1) Produce a self-contained interactive page.
python -m animageo docs/guide/assets/ggb/sample_triangle.ggb \
  -o /tmp/animageo-board.html

# Or write the pure-data board contract without touching test fixtures.
python - <<'PY'
from pathlib import Path
from animageo.animageo import AnimaGeoScene
s = AnimaGeoScene()
s.loadGGB("docs/guide/assets/ggb/sample_triangle.ggb", generate_stubs=False)
Path("/tmp/sample-triangle.board.json").write_text(
    s.exportJSXGraph(output="spec"), encoding="utf-8"
)
PY

# 2) Serve the repository and open a demo.
python3 -m http.server 8000
#   → http://localhost:8000/web/web-component/demo.html
#   → http://localhost:8000/web/adapters/vanilla.html

# 3) Run the JS tests (in another terminal, no extra dependencies).
npm --prefix web/runtime test
npm --prefix web/web-component test

# 4) Real-browser smoke against live JSXGraph (skips if no Chrome).
node web/runtime/scripts/browser-smoke/run.mjs
```

## Status

The spec contract, runtime, web component, and adapter examples are implemented
and tested. Static sampled curves do not yet resample on pan/zoom; the runtime
README documents that limitation and the recommended re-export strategy.
