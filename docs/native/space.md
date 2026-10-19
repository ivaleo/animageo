# Space (experimental): `animageo.native.space`

**Experimental.** The space registry `1.0`, the space document, the flat
scene `/1` and the fixtures may change without a deprecation period; the
plane (its registry `REGISTRY_VERSION`, `native.*`) does not change.
`native.has("space")` says that the package is there (an experimental
feature, outside `native.FEATURES` and the public API snapshot). The
browser kernel of the web app repeats §2–§5 in TypeScript; the fixtures
`animageo-space-parity/v1` (`parity/v1/space`) are the reference.

## 1. The document

A space document is `animageo-construction/v1` with `"space": "space"` and
`operationRegistryVersion` `"1.0"` — the version of the space registry,
a line of its own: the plane registry is `1.6`, a space document of `1.1`
is `newer_registry` for this library. `viewDefaults.camera` is the view of
the export (`projection` `orthographic` | `oblique` | `perspective`,
`azimuthDeg`, `elevationDeg`, `target`, `distance`, `oblique {angleDeg,
ratio}`); `viewDefaults.ground` (`look` `none` | `sheet` | `grid`, `size`)
is display only; `viewDefaults.bounds` is not written. The axis up is **z**,
the ground is `Oxy`. Inputs: `point3 [x, y, z]`, `pathParameter t`,
`surfaceParameter [u, v]`; the plane `point` input is refused.
`space.load`, `space.validate` (codes of the plane plus `space_unsupported`
for an operation of the plane).

## 2. The space registry 1.0

`animageo/native/ops/v1/space`: the groups `point3`, `segment3`,
`polygon3`, `plane`, `polyhedron`, `section`, the types and reasons added to
those of the plane, `INDEX.json` (`registryVersion 1.0`, `extends` — the
plane `REGISTRY_VERSION` whose catalogs it adds to, `1.6`;
`SPACE_REGISTRY_VERSION`). `registry index --check` checks both and says
`registry 1.6 (space 1.0)`. The plane registry does not read this folder.
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
`appearance.<id>.visible: false` — not drawn (a hidden solid hides nothing).

## 5. Drawing and style

`native.render(space_doc, …)` (or `space.render`) draws the flat scene as a
plane document (`space.to_document(flat, doc)`) with the same renderer:
SVG, PNG, PDF, EPS, TikZ. Pieces are segments `<id>--<k>`, fills polygons
`<id>`, points keep their IDs.

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

## 6. Fixtures and the flicker gate

`python -m animageo.native fixtures space [--check]` writes and replays
`parity/v1/space`: `space_values_*` (values by ID; a length within
`1e-9·S`, an area `S²`, a volume `S³`) and `space_flat_*` (a scene seen by
two or three cameras of a grid; numbers within `1e-9·max(1, scale)`).
Numbers are rounded to 9 decimals.

`space.flicker.flicker_events(doc)` walks the orbit (1°, elevations 0, 20,
89.5°, 32 samples per line): a `blink` is a view that changes for one step
and comes back (probed at ±¼ step; a line passing end-on is not one), a
`short` piece is under 0.9 px on a line of two or more pieces. The ten
degenerate scenes of `degenerate_scenes()` show none.
