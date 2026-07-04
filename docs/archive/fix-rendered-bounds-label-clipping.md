# Fix: rendered_bounds clips auto-placed edge/corner labels

## Problem

When exporting a construction with `content.source = "rendered_bounds"` (the tight
"fit canvas to drawn content" crop used by AnimaGeo Web exports) **and** a style
with label auto-placement enabled (`overlay.label_placement.enabled = true`),
the labels of points that sit at the extreme edges/corners of the figure are
**clipped off the canvas**. Interior labels render fine.

### Reproduced

Construction `e5fa3f5f-…` (web, prod): triangle `A,B,C` + incircle center `D` +
tangent point `E`, all 5 points visible with labels on, style "мой стиль 2"
(`label_placement.enabled = true`), export SVG 480px, `rendered_bounds`,
`padding = 0`.

- Export → only **D** and **E** labels appear; **A, B, C** (the corner vertices)
  are missing, even though `_make_label` fires for all five.
- Same export with `padding = 40` → all five labels appear.
- Same export with `label_placement.enabled = false` → all five appear (labels
  stay at default offsets, which the crop already covered).

## Root cause — ordering

`loadGGB()` runs in this order:

```
applyStyle(...)        # animageo.py — computes the rendered_bounds crop here
addAllGeometry(...)
autoPlaceLabels()      # moves labels OUTWARD from the geometry to avoid overlaps
```

`applyStyle` measures the rendered-bounds rectangle via
`_rendered_bounds_source_view()`, which builds each element's mobject (label
included) and takes its extent. But this runs **before** `autoPlaceLabels()`.
At measure time the labels are at their *default* offsets, so the crop is sized
for default-offset labels. `autoPlaceLabels()` then shifts the labels of edge
elements outward — past the now-frozen crop — and the export clips them.

Interior points (D, E) are unaffected: their outward offset still lands inside
the geometry's bounding box.

## Fix

Measure the rendered-bounds crop **after** label placement, so the canvas
reserves room for the final label positions.

`applyStyle` already sets up the source-view camera + import overrides before it
measures the crop. Factor the "measure crop → compute layout → set camera"
sequence into a local `_finalize_layout()` step and, for the `rendered_bounds`
path with placement enabled:

1. `_finalize_layout()` once (resolves an initial scale).
2. `autoPlaceLabels()` at that scale (writes pixel offsets to `elem.style`).
3. `_finalize_layout()` again — the crop now includes the placed labels.

Key correctness points:

- `_finalize_layout()` resets the camera to the **source view** before measuring
  so label/Tex extents convert MU→source-px at one consistent `ptUnit` (the
  existing single-pass code already relied on this).
- `apply_label_layout` writes offsets to `elem.style` (highest resolver
  priority), so the second measurement and any later render pick them up.
- `resolve_overrides_only` reads from `ggb_raw`, so import overrides are not
  re-applied destructively.
- Label offsets are stored in **pixels**, so re-fitting the crop (a small uniform
  scale change) does not move labels relative to their points — no re-placement
  needed, and no risk of an infinite loop.

Non-`rendered_bounds` sources (`ggb_view`, `source_view`) are unchanged: the
crop is the GeoGebra/reference view, which already has margins, and
`loadGGB`'s own `autoPlaceLabels()` still runs.

## Acceptance criteria

- Export of `e5fa3f5f-…` (SVG/PNG, `rendered_bounds`, `padding=0`, label
  placement on) shows **all five** labels A–E, none clipped.
- Labels are not noticeably worse-placed than before (no new overlaps).
- `ggb_view` / `source_view` exports are byte-for-byte unchanged.
- Regression test added that renders a corner-vertex construction with
  `rendered_bounds` + placement and asserts every visible-point label's bbox is
  inside the canvas.

## Release / deploy note

Bump `animageo` version and **publish the wheel to PyPI** before the web
`docker build` (which does `pip install .`) — the web app pins an exact
`animageo==<version>`. Same constraint documented in the animageo_web
deployment notes for the 1.3.0 export-formats rollout.
