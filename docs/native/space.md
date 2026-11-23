# Space (experimental): `animageo.native.space`

**Experimental.** The space registry `1.1`, the space document, the flat
scene `/1` and the fixtures may change without a deprecation period; the
plane (its registry `REGISTRY_VERSION`, `native.*`) does not change.
`native.has("space")` says that the package is there (an experimental
feature, outside `native.FEATURES` and the public API snapshot). The
browser kernel of the web app repeats §2–§5 in TypeScript; the fixtures
`animageo-space-parity/v1` (`parity/v1/space`) are the reference.

## 1. The document

A space document is `animageo-construction/v1` with `"space": "space"` and
`operationRegistryVersion` on a version line separate from the plane
registry. `SpaceBuilder` writes the lowest version needed by the document:
`"1.0"` for the original operations and `"1.1"` when a straight line or
projection is used. A later declaration such as `"1.2"` is reported as
`newer_registry`. `viewDefaults.camera` is the view of
the export (`projection` `orthographic` | `oblique` | `perspective`,
`azimuthDeg`, `elevationDeg`, `target`, `distance`, `oblique {angleDeg,
ratio}`); `viewDefaults.ground` (`look` `none` | `sheet` | `grid`, `size`)
is display only; `viewDefaults.bounds` is not written. The axis up is **z**,
the ground is `Oxy`. Inputs: `point3 [x, y, z]`, `pathParameter t`,
`surfaceParameter [u, v]`; the plane `point` input is refused.
`space.load`, `space.validate` (codes of the plane plus `space_unsupported`
for an operation of the plane).

## 2. The space registry 1.1

`animageo/native/ops/v1/space` holds the operation groups, types and
reasons. Its `INDEX.json` records the space registry version and the plane
`REGISTRY_VERSION` it extends. `registry index --check` checks both. The
plane registry does not read this folder. The signatures of the original
space operations remain at `1.0`.
An output may repeat by a formula: `count {per, times, plus}` —
`N = times · n(per) + plus`.

| op | inputs | outputs | reasons |
|---|---|---|---|
| `point3.free` | — (input `point3`) | `point` | — |
| `point3.on_path` | `path: path3` (input `t`, clamped to `[0, 1]`) | `point` | upstream |
| `point3.on_surface` | `surface: polygon3` (input `[u, v]`) | `point = P0 + u (P1 − P0) + v (Pn − P0)` | upstream |
| `point3.midpoint` | `a, b` | `point` | upstream |
| `segment3.by_points` | `a, b` | `segment {a, b, length}` | upstream |
| `polygon3.by_points` | `vertices[≥3]` | `polygon {vertices, normal, area}`, `side.k` | collinear_points, not_planar |
| `plane.by_points` | `a, b, c` | `plane {p, n}` (`n ∥ (b − a) × (c − a)`) | collinear_points |
| `polyhedron.cube` | `a, b` (an edge) | `solid`, `vertex.1…6`, `edge.1…12`, `face.1…6` | coincident_points |
| `polyhedron.prism` | `base[≥3]`, `top` (= `A_1`) | `solid`, `vertex.1…n−1`, `edge.1…3n`, `face.1…n+2` | collinear_points, not_planar, not_convex, flat |
| `polyhedron.pyramid` | `base[≥3]`, `apex` | `solid`, `edge.1…2n`, `face.1…n+1` | the same |
| `polyhedron.tetrahedron` | `a, b, c, d` | `solid`, `edge.1…6`, `face.1…4` | collinear_points, flat |
| `section.plane_polyhedron` | `plane`, `solid` | `section {polygon, faces}` | outside, touch |
| `line3.by_points` | `a, b` | `line {p, dir}` | coincident_points |
| `line3.parallel` | `point, line: lineCarrier3` | `line` | coincident_points |
| `line3.perpendicular_line` | `point, line: lineCarrier3` | `line` | coincident_points, point_on_line |
| `line3.perpendicular_plane` | `point, plane: planeCarrier3` | `line` | upstream |
| `point3.projection_line` | `point, line: lineCarrier3` | `point` | coincident_points |
| `point3.projection_plane` | `point, plane: planeCarrier3` | `point` | upstream |

A straight line has a unit `dir` and `p`, the projection of the world
origin onto the line. The direction follows `a → b`, the direction of
the parallel carrier, the direction from the source point to the foot
on a line, or the normal of the plane carrier. A point on the line
within the decide length has infinitely many perpendiculars, so
`line3.perpendicular_line` reports `point_on_line`. Its projection is
still defined.

A `lineCarrier3` is a straight line or the supporting line of a segment.
A `planeCarrier3` is a plane or the supporting plane of a polygon or
solid face. Projection can place a foot beyond the segment or outside
the face. A segment whose endpoints are within the decide length does
not define a carrier. These families are separate from the `path3` and
`surface` inputs of constrained points.

**Canonical order of a solid.** A prism over `A, B, …` has the vertices
`A …, A_1 …`; edges — the base, the top, then `AA_1, …`; faces — the base,
the top, then `ABB_1A_1, …`. A pyramid — the base and the apex; edges — the
base, then `AS, …`; faces — the base, then `ABS, …`. A cube is the prism on
the square `ABCD` over its edge `AB` (`AD` horizontal: `z × AB`, or `AB × x`
when `AB` is vertical; up `AB × AD / |AB|`); a tetrahedron `ABCD` is the
pyramid on `ABC` with the apex `D`. Only the vertices the solid makes are
outputs. A face ring that looks inside is reversed keeping its first vertex
(`ABCD` → `ADCB`): rings are counterclockwise seen from outside, normals
outward.

**Decisions.** The scale `S` is the diagonal of the box of the free points
(at least 1); the decide tolerance `1e-10·S` (a length): collinear —
area / diameter, planar — the largest distance to the plane of the ring,
flat — the height of the top or the apex over the base, convex — every
turn of the base counterclockwise about its normal and the turns adding up
to one full turn. A section: vertices within `1e-10·scale` of the plane are
on it; fewer than three distinct points → `touch`; all on one side →
`outside`; the polygon is counterclockwise about the normal of the plane,
`faces[i]` — the faces of the solid its side `i` lies on.

## 3. Projector and visibility

Formulas of `camera.py` and `visibility.py` (spec §3.2–3.3): orbit
direction `(cos el cos az, cos el sin az, sin el)`, sheet `r = (−sin az,
cos az, 0)`, `u = r × f`; oblique — `Oxz` true, `y` at `angleDeg` shortened
by `ratio`; perspective 1 : 1 in the plane of the target. A face is
`front` | `back` | `side` (cosine beyond `1e-10`); an own edge or vertex is
seen when one of its faces is `front`; any other line or point is hidden by
the shadow volume of a convex solid (behind every front face, inside the
side plane of every silhouette edge and side face; the boundary is in the
shadow); the side of a section takes the faces it lies on; planes hide
nothing. Pieces: hidden intervals merged, a gap or a bit shorter than
`0.9` px of the reference frame merges into its neighbour.

## 4. The flat scene `/1`

`space.flat_scene(doc, camera=None)` → `animageo-flat-scene/1` (docstring of
`space/scene.py`): `solids` far to near, `fills`, `strokes` with `pieces`,
`points`, `diagnostics`. Every `id` is an element ID of the document; a
`part` names a piece without its own element (`side.k` of a section,
`border.k`, `corner.k.j`, `trace` of a plane). Layers: `rank·10 + tier`
(plane 0, back faces 1, sections 2, hidden pieces 3, front faces 4);
visible pieces at `(len(solids) + 1)·10`. `appearance.<id>.visibility`:
`auto` | `strict` (the rules) | `always` (never hidden);
`appearance.<id>.visible: false` — not drawn (a hidden solid hides nothing;
its section, if shown, is a plane figure — rank 0, no `solid`, its sides
hidden only by the solids that are drawn; 1.11.0rc8).

When the interiors of two drawn solids intersect, `diagnostics` includes
`{"code": "overlap_order", "id": "A", "otherId": "B"}` with their solid
element IDs in lexical order. The scene keeps the analytic edge and
section strokes and omits the face and section fills of the listed
solids. Plane sheets and other solids keep their fills. Face, edge and
point contacts keep the ordinary painting order. The test is bounded: a
point found inside both bodies proves an intersection, parallel edges
give one separating axis, and a pair that needs more than
`overlap.AXIS_BUDGET` vertex projections (very large bases) is listed
with `"approximate": true` — treated as intersecting without a proof.

The scene bounds are computed from drawn finite geometry, before
straight lines are clipped. A line contributes a stroke with its own
element ID and role `segment`. It contributes no pieces when it misses
the frame, lies behind the near plane or projects end-on. Perspective
clips at positive depth `1e-6 · scale` and uses the vanishing point as the
image endpoint of an unbounded forward interval. The clipped line uses
the same shadow volumes and visibility policies as the other strokes.
For a clipped line, the piece interval `t` is affine on the picture.

## 5. Drawing and style

`native.render(space_doc, …)` (or `space.render`) draws the projected scene
with the plane renderer for SVG, PNG, PDF, EPS and TikZ. Pieces are
segments `<id>--<k>`, fills polygons `<id>`, and points keep their IDs.
`space.to_document(flat, doc)` returns the plane geometry and its appearance.

Labels, points and strokes are in pixels of the sheet (1.11.0rc7): the
style pixels on the output, times `prominence`, whatever the frame reaches.
The source view of the plane document is the extent of the picture
(`viewDefaults.bounds` = `bounds` of the flat scene), so the default
`frame` decorations followed it — a large sheet of a section plane or
another camera made the labels up to twice as small. `space.render` draws
under `space.sheet_layout(export_layout)`: `content.decoration_scale_source`
`output` unless the layout names its own (`export_layout.py`); `None` stays
`None` (the canvas is the source view, its pixels are the style's). A
caller that draws the plane document of `to_document` itself passes its
layout through `sheet_layout` too. The scenes `section_cube_triangle` and
`section_cube_far_plane` of the fixtures are the pair the rule is checked
on (`test_native_space_render_manim.py`).

The style section `space` of `style_config`
(spec §3.5; it joins the style schema after P2):

| key | default |
|---|---|
| `hidden.look` | `dashpale` (`dash`, `pale`, `thin`, `both`, `none`) |
| `hidden.stroke_dash_ratio`, `hidden.stroke_dash_period_px` | `0.55`, `8` |
| `hidden.stroke_opacity`, `hidden.stroke_width_scale` | by look: `0.55` (pale), `0.5` (thin), `0.45` / `0.6` (both) |
| `face.look`, `face.fill`, `face.fill_opacity_front`, `face.fill_opacity_back` | `flat`, `presets.color.shade`, `0.5`, `0.5` |
| `section.stroke`, `section.fill`, `section.fill_opacity` | `presets.color.accent`, `presets.color.accent_light`, `0.7` |
| `plane.look`, `plane.fill`, `plane.fill_opacity`, `plane.stroke` | `sheet`, `presets.color.shade`, `0.6`, `presets.color.aux` |

The paint of a hidden piece is the paint of its element (`resolve_paint` of
the piece as seen) with the look: opacity × the multiplier, width × the
scale, dashes. `appearance.<id>.overrides.hidden_look` — the look of one
element. `face.look: lit` is drawn as `flat` for now.

### 5.1 Paint and projected labels

`space.resolve_paint(doc, style_config=None, *, camera=None, inputs=None,
export_layout=None)` returns `animageo-space-paint/v1`:

- `bounds` is the flat frame in picture units, y up. `ptUnit` converts
  these units to sheet pixels. `ptUnitStyle` converts decorations from
  style pixels to picture units by division. A crop of the rendered
  bounds with labels uses the same approximation as plane paint. The
  actual export lays out and measures the scene before drawing marks.
- `strokes` keeps the flat scene's `id`, `part`, `role` and piece order.
  Each piece keeps `a`, `b`, `t`, `layer` and visibility information,
  and adds its one-based `index` and `stroke`. The stroke contains
  `color`, `opacity`, `widthPx`, `cap`, `z` and `dash` from
  `native.resolve_paint` of the plane piece. Its dash fit is calculated
  for that piece's length. `stroke: null` represents a piece with
  no painted stroke, including a hidden piece with look `none`.
- `fills` keeps the flat fill data and adds `fill`. `points` keeps the
  flat point data and adds `point`, `stroke`, `fill` and `z`.
  `background` is the resolved plane background.
- Each `labels` entry is `{id, kind, at, label}`. `kind` is `point`,
  `stroke` or `fill`, and `at` is the plane label spot in picture
  units. Explicit `name` and `caption` labels of lines, faces,
  planes and sections attach once, to a visible fill or the longest
  visible stroke piece. Front faces supply fill anchors, and a section
  needs a visible side. `none` disables the label. Points keep the
  plane label behavior.
- `marks` contains resolved decorations described below.

### 5.2 Construction marks and split rendering

A visible midpoint on a drawn segment gives ticks on the two actual
halves, centered at the projected world quarter points. A hidden half
contributes no tick. Equal original lengths reuse a count. New classes
take one, two and then three ticks in dependency order, with subsequent
classes using three. Tick length, width, spacing and color use the visible
carrier's segment paint. A perpendicular can give a right-angle corner
at its real foot, with sides on the perpendicular and on the support.
The two projected arms are scaled in sheet pixels, then the corner of
their world parallelogram is projected through the same camera. A hidden
foot, an end-on angle or a corner that cannot fit its visible carriers
omits the mark. The per-element `right_angle_size_px` and
`right_angle_marker` can size or suppress it.

Space `viewDefaults.autoMarks.equalities` and `rightAngles` default to
true. `suppressedMarks` disables an individual mark with
`{source: operationId, kind: 'equal_segments' | 'right_angle'}`.
The operation ID is that of the midpoint or the perpendicular.

```python
ev = space.evaluate(doc, inputs=inputs)
flat = space.flat_scene(doc, camera, evaluated=ev,
                        plane_look=space.space_style(style_config)['plane']['look'])
prepared = space.prepare_render(flat, doc, style_config=style_config, evaluated=ev)
result = space.render_plane(prepared['document'], out, marks=prepared['marks'],
                            style_config=style_config, export_layout=layout, fmt='svg')
```

`prepare_render(flat, doc, *, style_config=None, evaluated=None)` returns
a plain JSON object `{document, marks}`. Pass the same `evaluated` as
for the flat scene when overriding inputs. `marks` is a closed
`animageo-space-marks/v1` sidecar `{format, camera, scale, guides}`.
Each guide names a projected segment (`planeId`), its `layer` and
source operation. A ticks guide gives `half`, `count`, the projected
center `at` and tangent `direction`. A right-angle guide gives the world
`foot` and unit `arms`, the point-to-foot `length`, projected
`reach` along the two visible carriers and an optional style override
`sizePx`. This is render-job data derived by the space kernel. The
check refuses a sidecar whose numbers are not finite, whose positions
(`at`, the projected `foot`) lie off the sheet (`viewDefaults.bounds` of
the plane document widened by its size on every side), whose tick
`direction` or `reach` is longer than twice that size, or whose
`planeId` is not a segment of the sheet; the projection drops any stroke
that would not be finite.

`render_plane(plane, out=None, *, marks=None, fmt='svg', style_config=None,
export_layout=None, report=True)` validates the sidecar and draws its
strokes on the final sheet before placing labels.
`layout_plane_labels(plane, *, marks=None, style_config=None,
export_layout=None, backend='metrics', place=None)` adds the same strokes
to the existing plane label solver's obstacles. It returns the usual
plane label layout keyed by plane ID.

With a sidecar and reporting enabled, the render report includes
`spaceMarks` with the emitted records. The same records appear in
`space.resolve_paint(...)["marks"]`. Each carries `kind`, `source`,
`layer`, `z`, `color`, `opacity` and `widthPx`. Ticks also give
`half`, `count`, `at`, `lengthPx`, `shiftPx` and
`lines: [[x1, y1, x2, y2], ...]`. The corner gives `sizePx` and
`corners: [foot, along, corner, across]` in picture units. Its two
painted strokes are `along → corner → across`.

## 6. Fixtures and the flicker gate

`python -m animageo.native fixtures space [--check]` writes and replays
`parity/v1/space`: `space_values_*` (values by ID; a length within
`1e-9·S`, an area `S²`, a volume `S³`) and `space_flat_*` (a scene seen by
two or three cameras of a grid; numbers within `1e-9·max(1, scale)`).
Numbers are rounded to 9 decimals. The additive `space_values_lines` and
`space_flat_lines` fixtures cover registry 1.1, including feet outside the
carriers, degenerate carriers, near-plane clipping and the shadows of
solids. The seven registry 1.0 fixtures keep their original JSON; the
historical future-version probe is evaluated with an actually newer
declaration during replay.

`python -m animageo.native.space.paint_fixtures [--check]` writes or checks
`parity/v1/space_paint/space_paint_pieces.json`
(`animageo-space-paint-parity/v1`). Every case supplies the document,
camera, style and sheet layout with resolved paint, rounded to nine
decimals. The cases cover overlapping solids, hidden-piece looks,
visible and hidden lengths, roles, label anchors, and marks in oblique
and perspective cameras.

`space.flicker.flicker_events(doc)` walks the orbit (1°, elevations 0, 20,
89.5°, 32 samples per line): a `blink` is a view that changes for one step
and comes back (probed at ±¼ step; a line passing end-on is not one), a
`short` piece is under 0.9 px on a line of two or more pieces. The ten
degenerate scenes of `degenerate_scenes()` show none.
