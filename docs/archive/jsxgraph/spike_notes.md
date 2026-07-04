# JSXGraph export — Phase 0 spike notes

Phase 0 de-risks the architecture in `docs/archive/jsxgraph_export_plan.md` before
building the generic pipeline. Artifacts: `spike.html` (self-contained page) +
`spike.js` (the board, the shape Phase 1 must auto-generate).

## How to run

```bash
cd docs/jsxgraph && python3 -m http.server 8000
# open http://localhost:8000/spike.html
```
(Serve over HTTP rather than `file://` so the relative `spike.js` and CDN
assets load cleanly.)

## Confirmed programmatically (this session)

- **Input classification is sound for the target case.** On a real GGB import
  (`examples/ex_general.ggb`) `Construction.get_independents()` returns
  `A,B,C → free_point` and `G → tparam_point` — exactly the draggable set Phase 1
  maps to points/gliders/sliders. The keyframe system already relies on this, so
  it is well-exercised.
- **Coordinates need no conversion.** Element coords are math units (MU);
  JSXGraph works directly in MU with a `boundingbox = [left, top, right, bottom]`
  taken from `AnimaGeoScene._get_scene_bounds()`. Style *sizes* (point size,
  stroke width) are pixels in both systems — also no conversion.
- **`spike.js` parses** (`node --check` OK).
- **Pinned CDN assets resolve** (HTTP 200): `jsxgraph@1.10.1`
  (`jsxgraphcore.js` + `jsxgraph.css`) and `mathjax@3` (`tex-svg.js`).

## Finding to carry into Phase 1 ⚠

**DSL `Point(x, y)` and `Point(circle)` do _not_ surface as `free_point` /
`tparam_point` independents.** They carry a literal input-command (`point_ii`,
`point_c`), so `get_independents()` (which requires *no* input command for a
free point) skips them. A DSL-built spike construction reported only the bare
`number` (`r`) as independent.

Implication: the Phase 1 builder should target **GGB-imported scenes** (where
detection works), or `get_independents()` must be extended to also treat
literal-constructed DSL points as free/glider. Decide at Phase 1 start; GGB
import is the primary use case, so targeting it first is fine.

## Element mapping confirmed for `command_map` (Phase 1, Tier A)

| AnimaGeo | JSXGraph `create(...)` | Notes |
|----------|------------------------|-------|
| `free_point` | `point [x, y]` | draggable |
| `tparam_point` (circle/line) | `glider [x, y, parent]` | **seed with coords**, not raw tparam |
| `number` / `measure` | `slider [[x1,y1],[x2,y2],[min,start,max]]` | |
| `boolean` | `checkbox` | (to wire in Phase 1) |
| `Midpoint(A,B)` | `midpoint [A, B]` | live |
| `Segment(A,B)` | `segment [A, B]` | live |
| `Circle(A,B)` | `circle [A, B]` | centre A through B |
| `Circle(M, r)` | `circle [M, () => r.Value()]` | **function radius** = live Tier-V value |

Labels: element `name` set to LaTeX (`'$A$'`) with `label:{useMathJax:true}`;
text via `create('text', […, '\\(…\\)'], {useMathJax:true})`. MathJax configured
in the HTML head before loading `tex-svg.js`.

## Browser check — DONE (headless Google Chrome, Phase 1 output)

Verified the **generated** Phase 1 export (`exportJSXGraph` on
`examples/ex_general.ggb`), not just the hand-written spike, via headless Chrome
(`--headless=new --screenshot` + a `--dump-dom` drag probe):

- [x] Board renders cleanly — triangle, points, bisector, perpendicular, angle
      arcs, glider on a line, intersections. **No JS errors** (`window.onerror`
      null; 82 JSXGraph objects built).
- [x] **MathJax labels typeset** (`A B C M L H G` as italic math). This caught a
      real bug: `resolve_label_text` returns `$A$`, which I double-wrapped into
      `\($A$\)` → literal `$A$` on screen. Fixed by `style_map.label_name`
      (strip `$…$`/`\(…\)`, then wrap once). Regression test added.
- [x] **Live propagation confirmed**: dragging free point `A` `[-4,-1]→[-7,1]`
      moved the glider `G` (on the live angular bisector `f`)
      `[2.571,1.758]→[0.112,1.456]`. The dependency graph recomputes in-browser.
- [x] Static chain correctly does **not** propagate (a point whose ancestors go
      through the static polygon stays put) — matches the documented v1 limit.

Remaining manual nicety (optional): open in a real browser and drag by mouse to
feel the UX; the automated probe already proves the wiring.

## API points to confirm during Phase 1 (drift risk)

- Exact MathJax option key (`useMathJax` vs `useMathjax`) for the pinned version;
  whether name needs `$…$` or JSXGraph wraps it.
- `ray` → `line` with `straightFirst/straightLast`; `parallel`/`perpendicular`
  creator signatures; `intersection(a, b, index)` branch selection.

## Decisions locked for Phase 1 (from review)

1. Output: **self-contained HTML** (CDN JSXGraph + MathJax) — this spike is the
   shape to generate.
2. Scope: **school/competition core ~30** (Tier A).
3. Fallback: **static element + coverage report** (flag elements that won't
   track drags).
4. Labels/assets: **MathJax + CDN** (pin `jsxgraph@1.10.1`, `mathjax@3`).

## Verdict

Architecture is sound: coordinate/boundingbox model is trivial (MU direct),
the input→widget mapping matches `get_independents()` for GGB scenes, the core
creators and MathJax/CDN scaffold are in place and load. **Proceed to Phase 1**,
carrying the DSL-independents caveat above. The only items pending are
browser-visual confirmations (checklist above), which need an interactive
session.
