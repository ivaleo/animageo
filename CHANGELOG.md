# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Parity scene `l2_reasons`: the undefined reasons of registry 1.2–1.4
  operations that no other scene reached (`parallel` and `zero_length` of
  `intersect.line_sector`, `coincident`, `concentric` and `zero_length` of
  `intersect.nearest`, `zero_length` of `line.perpendicular`,
  `invalid_parameter` of `polygon.regular_center`, `coincident_points` of
  `sector.on_circle`, `collinear_points` of `sector.three_points`); a test
  now asks every reason of every operation to be reached by that
  operation.
- Classic dispatcher: signature aliases. When a command has no
  implementation for the exact input types, a segment or a ray stands for
  its carrier line (`Slope`, `AreParallel`, `ArePerpendicular`,
  `AreConcurrent`, `AngleBisector`, `Tangent`, `Polar`, `Line`,
  `OrthogonalLine`, `PerpendicularLine`, and the axis of `Mirror` /
  `Reflect`), a circle stands for a conic, and a conic that is a circle (a
  circle given by its equation) for a circle. So `Slope(s)` of a segment,
  `Tangent(l, c)` (tangents to a circle parallel to a line) and
  `Mirror(A, x² + y² = 4)` now build; signatures that had an
  implementation are untouched. `lib_commands.signature_alias`.
- Style defaults for `locuscurve` (`style/builtin.json`): a locus gets the
  stroke colour and width of the other curves instead of the renderer
  fallbacks.

### Fixed

- `Tangent(A, c)` from a point inside the circle is undefined, as in
  GeoGebra; it used to give the polar of the point as a "tangent". On the
  circle it is still the tangent at the point.
- `Vector(v, k)` (`vector_vi`) runs from the start of `v`; the ends used to
  be scaled from the origin.
- `Rotate(v, α, O)` of a vector turns both ends about `O`; the centre used
  to be ignored (the vector turned about its own start).
- `CircleSector.contains` (it returned `None`): a point is on a sector when
  it is on its arc or on one of its two radii; `Intersect` filters with a
  sector now work.
- `Intersect(line, sector)` also finds the points on the two radii of the
  sector (after those on the arc, without repeating a shared point); it
  used to intersect the arc only.
- `AngleBisector(l1, l2)` of parallel or coincident lines is undefined
  without an error in the log (it raised inside the command).

## [1.8.1a5] - 2026-10-05

### Added

- Registry 1.4 of `animageo.native` grows (1.8.1a5; records with `since:
  "1.4"` may still change until 1.8.1, earlier records do not):
  - `angle.between_lines` — the convex angle between the directions of two
    linear inputs at the crossing of their carriers (`parallel`,
    `coincident`); `angle.between_vectors` (beta) — counterclockwise from
    the first vector to the second at its start; `angle.by_size` — GeoGebra
    `Angle(A, V, α)`: the angle and the point `A` turned about `V`;
  - `number.angle` — a free angle parameter (input kind `angle`, radians,
    `0` when absent; params `min`, `max`, `step`), `unit: "angle"`;
  - measures with a unit: `measure.length` (segment, vector, polyline,
    arc), `measure.distance` (point to a point or a path),
    `measure.area` and `measure.perimeter` (polygon, disc, sector),
    `measure.angle`, `measure.radius`, `measure.circumference`; output slot
    `number`;
  - families `measurable`, `bounded`, `figure`; six parity scenes
    `l2a5_*`;
  - `measure.polygon_angles` — the interior angles of a polygon, slots
    `angle.1…N` at vertex `k` (`vertex_index`);
  - transformations `transform.translate`, `transform.rotate`,
    `transform.reflect_line`, `transform.reflect_point` and
    `transform.dilate` of a `transformable` object (point, segment, ray,
    line, vector, circle, arc, sector, polygon): output `image` of the type
    of the object, and for a polygon also `side.i` and `vertex.k`; a
    reflection in a line reverses the orientation (an arc keeps its
    counterclockwise sweep, its ends swap), a dilation by `k ≈ 0` is
    `invalid_parameter`; mandatory checks against an independent map;
  - record field `like` on an output (the type of the element of that
    input; in the signature only when set, so earlier hashes stay) and a
    `repeat` that names a single reference input (the vertex count of that
    polygon, read from the slots of its producer); `output_type` and
    `output_slots` take the document graph; six more scenes `l2a5_*`;
  - `number.expression` — a number computed by a formula: the new argument
    kind `{"kind": "expr", "ast": Expr}` (document schema and structure
    check) holds a tree of AST v1 (`docs/native/expr.md`): numbers, `pi`,
    `{"ref": k}` into the list input `refs`, `+ - * / ^`, unary minus,
    `sqrt abs sin cos tan asin acos atan exp ln lg min max`; depth at most
    32, at most 256 nodes, integer literal powers up to 64. A tree outside
    these rules is the `validate` issue `formula` with a JSON pointer to
    the node and the state `error/formula`; evaluation walks the tree (no
    `eval`) and gives `out_of_domain` or `non_finite`. AST v1 is a subset
    of the planned AST v2, so v1 trees stay valid. Package
    `animageo.native.expr` (`problems`, `evaluate`, `to_text`); the type
    `expr` and the limits `expr` join `_types.json` and `_numeric.json`.
    «Команды» print the formula (`e = sqrt(a) + b^3`) with the warning
    `unprintable_operation`: the grammar has no expressions yet, the line
    reads back as `forbidden` and an edit keeps the operation;
  - `text.free` — a text at a point with inserts: the argument kind
    `{"kind": "template", "value": string}` (at most 1000 characters;
    schema and structure check), `{k}` inserts item `k` of the list input
    `refs` (a number or a point, family `insertable`), `{{`/`}}` are
    braces; a bad insert is the issue `formula`. The value type `text` is
    `{anchor, text, parts}` without markup; numbers print rounded to the
    param `decimals` (default 2) half to even, angles in degrees with `°`,
    points as `(x, y)`. The bridge draws it as a classic `Text`. «Команды»
    print `Текст("…", A, a)` with `unprintable_operation`.
  - `intersect.nearest` (beta) — GeoGebra `Intersect(a, b, <Point>)`: of
    the solutions of two curves (the base pair, its order and part filters)
    the one nearest to the point `near`; new policy `nearest_to` (a tie
    within `tol.decide` keeps the earlier solution); without a defined
    solution the reason of the pair; check `on_both`.

## [1.8.1a4] - 2026-10-05

### Added

- «Команды»: the warning `ambiguous_name`. When the name of an element also
  reads as two names of points of the document (an element `BC` next to
  points `B` and `C`), the name still means the element; `parse_commands`
  and `print_commands` both flag it, once, at the name on the left of the
  line that defines it, at the same line and column.
- `naming.json` has a `keys` section: raw names with their `name_key`.
- Registry 1.4 of `animageo.native` (30 operations, `docs/native/ops/`):
  - value types `arc` and `sector` (`{c, r, a0, a1}`, counter-clockwise,
    `a0 ∈ [0, 2π)`, `a1 ∈ [a0, a0 + 2π]`) and `polyline`
    (`{vertices, length}`); families `circular` and `curve` take an arc,
    `path` takes an arc, a sector and a polyline; new families `round`
    (circle, arc, sector) and `vertexed` (segment, polyline, polygon);
  - points: `point.divide` (ratio `m : n`), `point.center`,
    `point.closest`, `point.at_distance`, `polygon.vertex`;
  - lines: `line.angle_bisectors_of_lines`, `line.external_bisector`,
    `ray.at_angle`, `ray.by_vector` (beta), `line.tangents_from_point`,
    `line.tangent_at`, `segment.from_point_length`, `segment.midline`,
    `polyline.by_points`;
  - circles, arcs and sectors: `circle.diameter`, `circle.center_segment`,
    `circle.excircle`, `arc.center_two_points`, `arc.three_points`,
    `arc.semicircle`, `arc.on_circle`, `sector.center_two_points`,
    `sector.from_angle`, `sector.three_points`, `sector.on_circle`;
  - polygons: `polygon.regular` and `polygon.regular_center` (the side and
    vertex slots repeat by the param `n`), `polygon.parallelogram`,
    `polygon.centroid`;
  - `intersect.line_sector` with four fixed slots;
  - slot policies `tangent_side`, `bisector_kind`, `vertex_index` and
    `sector_sides`; mandatory checks for every new operation.
- The free input kind `angle` (`{"kind": "angle", "value": radians}`, the
  direction of `segment.from_point_length`). It may be absent and is `0`
  then; the input of a free operation belongs to the element of its first
  output slot.
- Path frames of an arc (`t ∈ [0, 1]`, clamped), a sector (`t` wraps into
  `[0, 3)`: the arc, then the radius to the centre and back) and a polyline
  (`t ∈ [0, n − 1]`, clamped), with `project` and `distance_to_path`.
- The bridge draws an arc as a classic `Arc`, a sector as a
  `CircleSector` and a polyline as a `LocusCurve`.
- 22 parity scenes `l2a4_*` (71 in all, 328 cases).
- Relations in `native.check(doc, checks=None, *, inputs=None,
  relations=None, trials=0, seed=None)` (`docs/native/checks.md`):
  `incident`, `parallel`, `perpendicular`, `equal_length`, `equal_angle`,
  `collinear`, `concyclic`, `concurrent`, `tangent` between elements, under
  the keys `relation:<id>`; an unknown predicate or argument type is
  `unsupported`. `CheckReport.details` says why a result is not decided.
- `general_position`: with `trials = N > 0` every check and relation must
  also hold in `N` re-evaluations with perturbed free inputs. The trials
  use a stdlib SplitMix64 generator seeded from `sha256` of the document ID
  (or `seed`) and the check ID, so the browser kernel repeats them bit for
  bit; a failed trial is reported as a counterexample.

### Changed

- An arc in `intersect.line_circle`, `intersect.circle_circle` and
  `intersect.other_than` is intersected as its carrier circle; then a
  solution off the arc leaves its slot `undefined/outside_part` with the
  arc's argument slot in `detail`.
- `validate`: `missing_input` no longer applies to an absent `angle` input
  or to the other outputs of a free operation; an input for an output other
  than the first is `input_not_free`.
- «Команды»: the operations of registry 1.4 have no Russian names yet and
  are printed by their IDs (`segment.from_point_length(A, 5, 0.6)`); the
  angle input prints as its last argument and defaults to `0`.

- `docs/native/commands.md` states that clients must give time-ordered IDs:
  the printer orders independent lines by operation ID.

## [1.8.1a3] - 2026-10-05

### Added

- «Команды», the text form of a construction document
  (`animageo.native.commands`, `docs/native/commands.md`):
  - `native.parse_commands(text, *, lexicon, base, id_factory, document_id)`
    builds a document from lines such as `M = Середина(A, B)`,
    `A = (0, 0)`, `r = 3`, `α = ∠ABC` or `X = Пересечение(c, d, не A)`;
  - a pair of points `BC` in an argument becomes a hidden segment or line
    (and `∠ABC` a hidden angle) that is printed back as `BC`;
  - outputs without a name on the left get the default names of the web
    canon, with school names for the sides of a triangle;
  - a line with an error is skipped, with an issue that carries a code, the
    line, the column in the text as typed, a Russian message and a hint; the
    document is built from the other lines;
  - the notation outside the subset (conditions, equations, functions,
    expressions, `key = value`, `около A`) is refused as «будет позже».
- `native.print_commands(doc)` prints a document as «Команды». The lines
  follow the topological order with ties by operation ID; free points and
  numbers have short forms; each call uses the first lexicon entry that
  reads back as the operation. `parse_commands(print_commands(doc).text)`
  rebuilds every parity scene.
- Edit mode: `parse_commands(text, base=doc)` changes a document to match
  the text and keeps IDs.
  - A changed coordinate or number becomes a new input value.
  - A changed definition goes through `redefine`; a refusal is an error of
    the line.
  - A removed line deletes its operation and what is built on it.
  - A line typed back unchanged keeps its operation exactly.
  - `effects` lists what changed.
- The lexicon `animageo-lexicon/v1` maps command names and aliases to
  operations, with the order of the arguments and how many are required.
  - Overloads are told apart by the number and the kinds of the arguments.
  - `lexicon_problems` reports ambiguous and unreachable overloads.
  - A copy of the lexicon for the operations of registry 1.3 ships with the
    library.
- Fixtures `animageo-commands/v1` (184 cases: parsing, pairs, overloads,
  names, numbers, every error code with its column, edit mode with
  effects) and `animageo-naming/v1` (default names), generated from
  templates for any lexicon:
  `python -m animageo.native commands fixtures --lexicon <file> -o <dir>`
  writes or `--check`s them, and `commands parse` and `commands print`
  help debugging.
- Default IDs of new operations and elements are time-ordered (the UUID
  version 7 layout), so independent lines print in the order they were
  typed.

## [1.8.1a2] - 2026-10-04

### Added

- Registry 1.3 of `animageo.native`: the angle by three points
  (`angle.by_points`, counter-clockwise from the first side as GeoGebra's
  `Angle(A, B, C)`; the value type `angle {vertex, a0, a1, size}` in
  radians), the incircle of a triangle with its centre and the three touch
  points (`circle.incircle`), and marks: equal segments and equal angles
  with one to three ticks or arcs (`mark.equal_segments`,
  `mark.equal_angles`, param `count`) and a right angle
  (`mark.right_angle`); the value type `mark {kind, count}`. A mark is
  defined whenever its arguments are; whether the claim holds is its check,
  so a failed check is a warning and the mark stays drawn.
- The bridge and `native.render` draw an angle as a classic angle (the arc
  of a DSL `Angle`), a right-angle mark with the right-angle marker and an
  equality mark as ticks or arcs on its targets (`tick_count`; an explicit
  override wins, and of several marks on one target the first in ID order).
  The render report box of an equality mark is the union of its drawn
  targets.
- `native.layout_labels(doc, …)` gives the label boxes of a document where
  `native.render` would draw them, without manim or LaTeX: the anchor, the
  offset in pixels and world units, the box, the leader, the labels and
  points it overlaps, whether the solver placed it and whether it is
  pinned. `place=True` runs the placement solver; a suggestion is kept by
  pinning `appearance.label.offsetWorld` and `overrides.label_anchor`.
  Labels are measured by setting their TeX with the metrics of the label
  template's fonts (`animageo/native/labels/metrics.v1.json`, rebuilt by
  `scripts/native/build_label_metrics.py`): on a corpus of 2000 labels the
  boxes equal manim's `Tex` within 1 %. `backend="tex"` measures with manim
  instead.
- The render report lists the labels that enter the marker of a drawn
  point, a label over its own point included (`pointOverlaps`,
  `[labelId, pointId]`); the format stays `animageo-render-report/v1`.
- Classic pieces usable without a scene: `label_placement.LayoutInput` (the
  placement solver reads it in place of an `AnimaGeoScene`),
  `label_placement.label_spot`, `label_size` and `ANCHOR_EDGES`;
  `export_layout.static_export_dict` (the export dict `applyStyle`
  computes) with `merge_reference`, `reference_size_from_config`,
  `source_bounds_px_from_config`, `source_view_from_bounds_px` and
  `rendered_view_from_bounds`; `geo.DRAW_ORDER` and `geo.is_drawn`;
  `style.config.style_path_for_geostyle`. `correctedLabel` moved to
  `animageo.labels` and is still importable from `animageo.ui`.
- 8 new parity scenes (49 in all) for angles, marks and the incircle.

### Changed

- `animageo.native` evaluates documents of registry 1.3; documents of
  registries 1.0–1.2 give the same results, the signature hashes of their
  operations did not change and their expectations changed only in
  `registry`. The fixture generator refuses cases near the jumps of an
  angle's direction and size between `0` and `2π` (the decisions
  `angle_wrap` and `zero_angle`, not noise decisions).
- Point labels of a construction document clear their marker: a point
  label that is not pinned and whose offset no style layer sets keeps
  `size_px / 2 + point_gap_px` decoration pixels between the centre of the
  point and the label box. Before, the anchor corner of the label sat on
  the point and the label covered it. The rule applies to
  `AnimaGeoScene.loadDocument` only (`native.render`, `python -m animageo
  doc.json`); `.ggb` files and DSL scenes keep the classic offset.
- The labels of elements a document does not draw (an undefined element,
  an equality mark, a number) are hidden, so automatic placement no longer
  avoids labels that are never drawn.

## [1.8.1a1] - 2026-10-03

### Added

- Registry 1.2 of `animageo.native`: the foot of a perpendicular from a point
  to a line, segment or ray (`point.projection`; the param `strict: 1` keeps
  the foot on the segment or ray itself), the parallel and the perpendicular
  through a point, the perpendicular bisector, the angle bisector (into the
  angle, numerically stable near a straight angle), a vector by two points,
  a circle by its centre and a radius (a number element or a number written
  in the document) and the circle through three points with its centre as a
  separate output; `number.free`, a free number with optional `min`, `max`
  and `step`.
- Document contract: the number input `{"kind": "number", "value": v}`, op
  params written as number literals in `args` (optional with a default, or
  required), number literals in input slots of type `number`; the value
  types `vector {a, b, length}` and `number {value, unit}`, compared in
  parity fixtures by their unit. Points on the new lines keep their place
  relative to the definition (the path frame of a perpendicular bisector
  starts at the midpoint).
- The document schema accepts a `workIntent` section (the problem text and
  its source, what the assistant must not do, assumptions, a brief
  revision) and `appearance.<id>.locked`; both are kept by load and dump,
  covered by `content_hash` and ignored by evaluation and rendering. They
  are additive: the format stays `animageo-construction/v1`.
- The bridge and `native.render` draw vectors as arrows; numbers are not
  drawn, and a free number is a classic `Var` holding the kernel value.
- 10 new parity scenes (41 in all) with 45 cases for the new operations.

### Changed

- `animageo.native` evaluates documents of registry 1.2; documents of
  registries 1.0 and 1.1 give the same results, the signature hashes of
  their operations did not change and their expectations changed only in
  `registry`.
- The render report box of an arrow covers its shaft as well as its tip.
- The fixture generator treats the rounding noise of a straight angle built
  from collinear points as exact (`straight_angle` joins `noiseDecisions`).

### Fixed

- `Circle(A, B, C)` through collinear or coincident points is undefined
  without an error in the log (the centre was looked up on a missing
  intersection).
- `AngularBisector(A, B, C)` with `A` or `C` equal to the vertex `B` (up to
  rounding, as in `Line(A, B)`) is undefined instead of a line made of NaN.

## [1.8.0a2] - 2026-10-03

### Added

- Registry 1.1 of `animageo.native`: a ray through two points, the
  intersections of a line, segment or ray with a circle and of two circles,
  "the other intersection point" (`intersect.other_than`, the explicit form of
  GeoGebra's reordering by a known point) and a point on a path (segment,
  line, ray, circle or polygon) given by a path parameter. Two-point
  intersections keep each solution in its own output slot by a documented
  rule, so a dragged point never swaps two elements and a vanished solution
  leaves its slot undefined; a tangency fills both slots and says so
  (`detail: {"multiplicity": 2}`). `intersect.line_line` accepts rays.
  `native.project(doc, id, (x, y))` gives the path parameter of the nearest
  point of a path.
- Pure document edits: `native.closure`, `dependencies` and `free_inputs`
  answer graph questions in topological order; `native.delete`, `redefine`
  and `rename` return the new document and a JSON-ready list of what changed,
  never change their input and refuse a broken result with
  `native.EditError`.
- `native.render(doc, style_config=…, export_layout=…, fmt="svg"|"png"|"pdf",
  out=…)` draws a construction document with the same renderer, styles and
  layout as a `.ggb` (`AnimaGeoScene.loadDocument`), applies the document's
  `appearance` (visibility, labels, style overrides) and returns a report
  `animageo-render-report/v1` with the pixel boxes of every element and
  label by element ID and the overlapping labels. `native.source_view(doc)`
  gives the source view of a document without manim.
- `python -m animageo doc.json -o out.svg` renders a construction document
  from the command line (SVG, PNG, PDF) with the usual placement and style
  flags; `--style-from-document` takes the style snapshot stored in the
  document.
- 22 new parity scenes (31 in all) for rays, circle intersections, the other
  point and points on paths; the fixture generator accepts the rounding noise
  of exact tangents and known points (`noiseDecisions`).

### Changed

- `animageo.native` evaluates documents of registry 1.1; documents of
  registry 1.0 give the same results and the signature hashes of the 1.0
  operations did not change.
- `python -m animageo` starts without loading the manim-backed API whatever
  its arguments, as it did for a `.ggb` argument.

### Fixed

- An intersection that gives fewer points than it has outputs leaves the
  missing outputs undefined: when a line touches a circle, the second point
  disappears instead of staying where the previous build put it.
- A circle with a zero or negative radius is undefined without an error in
  the log (`Circle(O, O)`, `Circle(O, 0)`, a radius from a zero segment); the
  `Circle` class no longer asserts a positive radius.
- `Line(A, B)` with `A` and `B` equal up to rounding (`|A − B| ≤ 1e-12` of
  their size) is undefined instead of a line in a random direction; a `Line`
  with a zero normal has the direction `(0, 0)`.
- Default positions are reproducible: a point on a circle, segment, line or
  ray without a parameter gets the same place on every run and keeps it on a
  rebuild. `Construction(seed=…)` sets the seed (0 by default, `None` for
  fresh randomness).

## [1.8.0a1] - 2026-10-03

### Added

- `animageo.native`, a new module that does not need manim: the construction
  document `animageo-construction/v1` and a reference geometry kernel.
  `native.load`, `validate`, `dump`, `dumps` and `content_hash` read and write
  documents (a JSON Schema ships in `animageo/native/schema/`);
  `native.evaluate` gives every element a value or a state (`defined`,
  `undefined`, `unsupported`, `error`) with a reason, and an element that
  depends on a broken one names the root cause; `native.check` runs the
  mandatory checks of each operation (`passed`, `failed`, `inconclusive`).
- The semantic operation registry `ops/v1` (registry version 1.0): free point,
  midpoint, segment and line through two points, circle by center and point,
  intersection of two lines or segments, polygon with its sides. Each record
  has a signature hash; `INDEX.json` lists them. The formulas, tolerances and
  degenerate cases are documented in `docs/native/`.
- Canonical JSON (`native.canonical_json`): numbers are written as JavaScript
  writes them, keys are sorted, so the same document gives the same bytes and
  the same hash in Python and in a browser.
- Parity fixtures `parity/v1`: nine scenes with expected values, states and
  check results, and the command line
  `python -m animageo.native fixtures generate|verify`, `registry index
  [--check]`, `evaluate` and `validate`. The generator refuses inputs that lie
  closer than 1000 decision tolerances to a degeneracy threshold.

### Changed

- `import animageo` skips the manim-backed API when manim cannot be found
  (before, it started importing it and stopped at the missing manim), and
  `python -m animageo.native` never imports it. `animageo.geo` now loads its
  modules in a working order by itself, so `import animageo.geo.lib_elements`
  still works without manim. With manim installed nothing changes; the
  classic API is the same as in 1.7.13.

## [1.7.13] - 2026-10-01

### Added

- A formula reads the typographic minus `−`, the multiplication signs `·` and
  `×`, `÷`, `π` and `ℯ`, so a formula copied from a textbook or a web page
  works as typed: `f(x) = 2πx − 1`, `y = ℯ^(−x^2)`, `x·y = 1`. `π` and `ℯ` are
  the constants even where the construction has objects named `pi`, `e` or `E`.
- In the DSL, `Line("y = 2x + 1")` builds a line from its equation, and
  `a = 2` then `Line("y = a x + 1")` follows `a`, as in a GeoGebra file.
  `Line(A, B)` and the other forms are unchanged.

### Fixed

- A formula that is only a coordinate of a point — `y = x(A)`, the line
  `x = x(A)` — builds again; it failed since 1.7.11.
- A graph of `tan`, `cot`, `sec`, `csc` or their hyperbolic counterparts no
  longer hangs while its asymptotes are found; the graph still breaks at every
  asymptote within |x| ≤ 1000.
- In the DSL, a boolean computed by a command (`b = AreCollinear(A, B, C)`)
  works in a formula again. A boolean is a condition in `If(b, x, -x)` and
  counts as 0 or 1 elsewhere (`y = x + b`), in functions, implicit curves and
  conics alike, from the DSL and from a GeoGebra checkbox.
- A GeoGebra formula with a number right before a name, `f(x) = 2a x`, follows
  the number `a`; it used to be imported as a fixed graph.
- `round` rounds halves away from zero, as GeoGebra does (`round(2.5) = 3`,
  `round(-2.5) = -3`), and `y = round(x)` is a graph.
- In the DSL, a comment after `f(x) = …` is no longer read as part of the
  formula.
- The length limit of a formula (4000 characters) applies to the text after
  `π` and `ℯ` are expanded, so a long run of them is refused at once.

### Documentation

- The documentation describes 1.7.12 and 1.7.13 throughout (formulas, labels
  placed in GeoGebra, keyframe labels, dashes); references to design notes that
  are not in the repository are removed from the code and the changelog.

## [1.7.12] - 2026-09-30

### Fixed

- The `*` may be left out of a formula: `f(x) = 2x + 1`, `k x`, `2(x + 1)`,
  `(x + 1)(x - 1)`, `x (x + 1)` and `2x(A)` (twice A's x-coordinate) are read
  as products, as GeoGebra reads them. `x(A)` with no space before the bracket
  is still A's x-coordinate, and `k(x + 1)` with a number `k` is a product.
- A number or slider named like a mathematical constant or function — `E`, `N`,
  `S`, `O`, `I`, `gamma` — can be used in a formula (`f(x) = E x + gamma`,
  `N(x + 1)`); such formulas used to fail to parse or, for `N(…)`, `S(…)`,
  `O(…)`, silently mean something else.
- A function that calls another one with a restricted domain,
  `f(x) = g(x) + 1` or `g(g(x))`, is undefined wherever `g` is, instead of
  extending `g`'s formula past its domain.
- In the DSL, `g(t) = 2t + 1` and `g(t) = t(t + 1)` define functions of `t`.

### Changed

- A formula calls only mathematical functions (`sin`, `sqrt`, `exp`, `log`,
  `abs`, `floor`, `gamma`, `erf`, …); any other name it calls is an object of the
  construction. `(x^2 + x)/x = y` is no longer read as a conic (the conic
  equation has to be a polynomial as written).

### Security

- A formula that asks for a huge exact computation is refused at once instead of
  stalling the load of an uploaded file: powers and roots (`7^(9^9)`,
  `root(7, 1/10^9)`, `sqrt` of a 30 000-bit number), factorials (`(10^7)!`),
  `exp(10^9 log(7))`, `floor`/`round` of a number beyond 1e308, `re`/`im` of a
  power with a huge exponent, and conic equations of too high a degree
  (`(x + y)^10000 = 1`). Sympy's integer functions (`fibonacci`, `binomial`, …)
  and number constructors (`Float(1, 10^9)`) are not callable, and formula text
  is limited to 4000 characters. Formulas are still evaluated exactly by sympy,
  so a service parsing uploaded files should keep a time limit on it.

## [1.7.11] - 2026-09-30

### Fixed

- A graph whose formula reads point coordinates is drawn and follows the points:
  `g(t) = y(A) (t - x(B)) (t - x(C)) / … + …` (a Lagrange polynomial through
  A, B, C) or `f(x) = x(A) + x` is rebuilt whenever a point moves. Such graphs
  used to vanish from the preview and every export. `x(v)`, `y(v)` of a vector
  work the same way, and so do conic, line and implicit equations
  (`(x - x(A))^2 + (y - y(A))^2 = 4` follows `A`).
- A function's variable is the one named on the left: `g(t) = t²` is the graph of
  `t²`; it used to be read as a function of `x` with an unknown `t` and was not
  drawn.
- A function that calls another one, `f(t) = g(t) + k (t - x(A))`, is built and
  follows `g`; it used to be dropped (or frozen at the load-time values).
- A function or implicit curve that cannot be read is reported in
  `command_diagnostics` (`expression_parse_error`) instead of only in the log.
- A graph between two points, `f(x) = If(x(A) ≤ x ≤ x(B), x²)`, is built and
  follows them.
- In the DSL, `Function("y = x(A)*x")` and `f(x) = g(x) + 1` follow `A` and `g`
  the same way.
- A DSL line that defines a name from itself (`A = Midpoint(A, B)`,
  `f = Function("y = f(x) + 1")`) raises a dependency-cycle error instead of
  hanging.

### Security

- Functions calling functions are inlined only up to a size limit: a chain such
  as `h_k(x) = h_{k−1}(sin x) + h_{k−1}(cos x)`, which doubles at every level,
  is cut with an `expression_parse_error` diagnostic instead of stalling the
  load of an uploaded file.

## [1.7.10] - 2026-09-26

### Added

- The dash period is set in style pixels: `stroke_dash_period_px` (per element,
  in `overlay`, `defaults` and `import.policy`; animatable in keyframes) and the
  style-wide `rendering.dash_period_px` (default 10). `stroke_dash_ratio` is the
  dash's share of the period: 0.65 of 10 px draws 6.5 px dashes and 3.5 px gaps.

### Changed

- A dashed line is exported as one line with a dash pattern — `stroke-dasharray`
  in SVG, a native dash in PDF and EPS — instead of a row of separate pieces, so
  other editors can restyle it and the files are smaller. Video frames draw the
  same pattern.
- Dashes are sized like line widths: they follow the style's prominence and no
  longer grow when the GeoGebra applet is zoomed in (a ×2 zoom used to double
  every dash while the lines kept their width).
- A segment, a vector or an arc starts and ends with a dash, and circles and
  ellipses close without a seam; a ray's dashes start at its vertex. With round
  or square line caps the visible dash keeps its nominal length.
- A `stroke_dash_ratio` of 1 or more, or below 0, draws a solid line.

### Fixed

- Dashes are drawn on arcs, ellipses, parabolas, hyperbolas, function graphs,
  implicit curves and loci; there they used to be ignored.
- A dashed vector keeps its arrow tip.
- Interactive export (JSXGraph and the `animageo-board/v1` spec): every dashed
  line used to come out dotted; it now gets the nearest JSXGraph dash by its
  length in pixels.
- TikZ export draws the same dash as the picture, taken from the style's
  period, instead of a fixed pattern.
- A line-cap change made during an animation reaches the drawn line.

## [1.7.9] - 2026-09-26

### Fixed

- A graph or curve given by a formula with a slider follows the slider:
  `f(x) = a x²`, `p: y = a x²`, `g: y = a x + 1` and implicit curves are rebuilt
  from their formula with the current value whenever the number changes, so the
  exact frame and the video move with the applet. They used to be imported as a
  snapshot at the load-time value and stood still. A conic or line keeps the
  curve GeoGebra saved if its equation does not reproduce it. In the DSL,
  `f(x) = a*x^2` (and `Conic("…")`, `ImplicitCurve("…")`) follow `a` the same way;
  before, the function kept an unbound symbol.
- A point whose coordinates contain brackets, such as `F = (0, 1/(4a))` or
  `P = (1, f(1))`, is built and follows the numbers in it. It used to vanish from
  the scene (or stand still at its saved position).
- `Translate(P, a*u)` — a vector expression as a command input — is built and
  follows `a`; the translated object used to vanish.
- `Dilate` of a function, conic or implicit curve (`Dilate(f, a, O)`) is
  supported, together with `Translate` of these curves, `Reflect` in a point,
  and `Reflect` in a line / `Rotate` of a conic.
- `Point(path, t)` with a number — a point driven by a slider along a path — is
  built with GeoGebra's parameter: `t` runs over `[0, 1]` (clamped). On a circle
  or an ellipse it is the angle `−π … π` from the conic's first axis, chosen as
  GeoGebra chooses it (a tall ellipse starts from its vertical axis); a
  hyperbola is walked right branch first, then the left one; a parabola from one
  end to the other, oriented like GeoGebra's (`Parabola(F, d)` follows the
  directrix). On a segment `t` is the fraction from A to B, and on a function
  graph it spans the x-range of the view saved in the file.
- A formula may use any number of the construction, not only a slider: a
  length or distance (`Radius(c)`, `Distance(A, B)`), an area, an angle object
  (`Angle(A, B, C)`) or a checkbox (`If(b, x, -x)`); moving a point that such a
  number depends on moves the graph. A point with a measure among its
  coordinates, such as `(0, -Radius(c))`, is built too.
- An object that still cannot follow the numbers it mentions is reported in
  `command_diagnostics` (`parametric_dependency_frozen`,
  `expression_parse_error`) instead of freezing silently. A `Point(path, t)`
  whose computed position disagrees with the one saved in the file keeps the
  saved position.

### Security

- Formula text from a `.ggb` file is no longer evaluated as Python: function,
  conic, line and implicit-curve formulas are parsed with a restricted
  namespace, and text that is not a formula (dunders, quotes, attribute access)
  is refused. Before, a crafted file could run code when it was loaded.

## [1.7.8] - 2026-09-21

### Fixed

- A label placed in GeoGebra stays next to the same part of its element when
  the export draws the figure at another scale than the applet (a small preview
  canvas makes labels relatively larger). The offset was replayed wholly in
  font space — right for a point, which has no extent, but a label parked near
  a segment's endpoint drifted far past it. Now an applet-placed label is
  re-attached to the point of its element nearest to where the applet drew it
  (`label_anchor.nearest_point`): that point scales with the figure, only the
  remaining offset stays in font space, so the gap to the line survives any
  font size. A label inside a region (polygon, sector, the inside of a circle
  or an ellipse) is attached to its own spot of the region. At the applet's own
  scale placement is unchanged; points are unaffected.

## [1.7.7] - 2026-09-21

### Fixed

- A label placed in GeoGebra lands where the applet drew it, for every element
  type GeoGebra has a label rule for — segments, vectors, rays, polygons,
  circles, ellipses, arcs and sectors, not only points. GeoGebra starts each
  label from a per-type base point (a segment's midpoint plus 16 px along its
  normal, a polygon's vertex average, a point on a circle's upper-left arc, …)
  and adds the stored `labelOffset`; the renderer started every non-point label
  from its own generic spot, so a segment label sat on the middle of its line.
  The rules now live in one table (`animageo/label_anchor.py`, transcribed from
  GeoGebra's `Draw*` classes) and are checked against label ink measured on the
  live applet (`tests/fixtures/label_anchor_types.*`, ≤ 2 px). Lines keep their
  previous placement — GeoGebra puts a line label relative to the applet window
  border, which an export frame does not have — and angles keep their own logic.
- Circles and ellipses draw their label; they drew none at all.
- A label that becomes visible during an interval (its element or the label
  itself hidden at the interval's start keyframe) appears already at its
  auto-placed position instead of at the unplaced default for the whole
  interval.
- Keyframe label snapshots run only with auto-placement enabled
  (`overlay.label_placement.enabled`). With it off they still ran whenever
  `keyframe_snapshots` was set and overrode hand-placed label offsets.
- With snapshots on, they own every label position: a keyframe's own
  `label_offset_px` style track no longer fights the snapshot interpolators, and
  a label first placed at a later keyframe gets the snapshot's anchor and
  auto-placed flag, so its offset is read in the solver's convention.
- `apply_keyframes_at` (single-frame preview) places labels from the same
  keyframe snapshots as playback, computing only its interval's two.

## [1.7.6] - 2026-09-21

### Fixed

- An element that is undefined in the loaded `.ggb` and becomes defined later
  (during an animation, or after a DSL/value change) now draws on its own layer.
  GeoGebra saves such an element with `NaN` coordinates — e.g. an intersection
  with a circle that does not exist in the saved state — and the parser created
  it without data, so it never received the defaults its type carries
  (`z_index`, label defaults). Once a rebuild defined it, it rendered on the fill
  tier: a point under the segments drawn through it. The first build now seeds
  the missing type defaults as intrinsic (non-explicit) style keys; values
  written while the element was undefined are kept.

## [1.7.5] - 2026-09-21

### Fixed

- The `grow` / `shrink` enter–exit effects keep a labelled element in place.
  Element mobjects are `VGroup([geometry…, label])`, and the effect scaled the
  whole group about its bounding-box centre, which sits between a point and its
  label: the dot started off-position and slid into place while growing, and the
  label shrank to nothing with it. The geometry now scales about its own centre,
  and the label stays where it stands and fades instead.

## [1.7.4] - 2026-09-05

### Fixed

- A point on a path whose path is written inline keeps the position GeoGebra
  saved for it. `Point(Circle(A, 1/2))` — a path that was never given a name of
  its own — was looked up under its raw expression string, which resolves to
  nothing. The point was then treated as an ordinary command output: its
  serialized `<coords>` were skipped and no path parameter was derived, so it
  landed at the arbitrary angle `point_c` falls back on when no parameter is
  given (a random value in `[0, 1)` radians). Every load placed such a point
  somewhere else, and the geometry built on it came out rotated by a different
  amount each render. Named paths (`Point(c)`) were never affected.

## [1.7.3] - 2026-08-31

### Fixed

- A degree suffix on a numeric GeoGebra variable (for example `K°` in a
  `Rotate` command) is parsed as an angle value rather than as part of an
  object name. This completes the non-identifier handling introduced in 1.7.2
  without breaking compound angle expressions.

## [1.7.2] - 2026-08-31

### Fixed

- GeoGebra labels containing non-identifier suffixes such as the degree sign
  (for example `K°`) are normalized consistently in element names and
  expressions. They no longer leak invalid characters into generated Python
  DSL or make thumbnail/export rendering fail.

## [1.7.1] - 2026-08-17

### Changed

- `docs/styles.md`: new §16 "Sizing & proportions" — the calibrated ratio
  system between size families (line width / point size / font / angle
  radius), canvas-scaling rules, the `content.prominence` dial and
  `decoration_scale_source` modes, and density adjustments for dense/sparse
  figures.
- `AI_USAGE_PROMPT.md`: principles-first revision — a new §0 "Working
  principles" (ten distilled rules the rest of the guide instantiates), a
  sizing-principles block in §7 (ratios, framing-vs-style diagnosis,
  `prominence`), compressed worked examples (§6 recipes, §11 sketch), and a
  known-limit note on angle value labels after motion. Validated end-to-end
  by context-free external-agent runs (codex gpt-5.6-sol / gpt-5.5,
  DeepSeek v4-pro chat API): 9/9 tasks produced correct figures/animations
  with the shipped guide, plus a re-validation run against the revised one.
- `AI_USAGE_PROMPT.md`: two fixes driven by a 10-case gallery re-validation —
  §4 warns that unbounded curves (parabola/hyperbola/function/`Line`) break
  `fitView` (the semantic core collapses to a few pixels) and prescribes an
  explicit viewport or extent points; §9 adds mandatory numeric frame checks
  for agents that cannot view images (a `to_px` mapping from
  `scene.style.export`, on-canvas margins, minimum pixel distance between
  key points, per-axis span share), with a matching troubleshooting row.

## [1.7.0] - 2026-08-11

### Changed

- Public-release documentation and packaging overhaul: internal working
  materials removed from the repository, core docs translated to English,
  packaged style presets (`style='default'`, `book_*`) resolvable by bare
  name, PyPI project URLs, `py.typed`, CI and GitHub Pages workflows, and
  corrected Apache-2.0 metadata for the source-distributed web packages.
- The declared Python floor is now 3.11, matching the mandatory
  `manim>=0.20.1` dependency. The previous `>=3.10` metadata described an
  installation that pip could not resolve.

### Fixed

- The CLI accepts packaged style names such as `--style default` and no longer
  writes `<construction>_stubs.pyi` beside input files during one-shot exports.
- Auto-placement now treats collision clearance as a hard constraint when
  `respect_current_position` is enabled. If a manual GeoGebra offset lies on
  geometry or another label, the solver preserves its side as a preference
  but moves it to the nearest reachable clear position instead of pinning or
  recompacting it back onto the obstacle.

## [1.6.5] - 2026-08-11

### Fixed

- **Manual GGB label offsets now reproduce the applet's label positions.**
  GeoGebra draws a point label with
  its left edge on the baseline at `(x + 4, y − 2·pointSize) + labelOffset`
  screen px — the stored offset is relative to that up-right base. The
  renderer instead anchored the label by the style anchor (web styles: `BC`,
  bottom-center) at the bare point centre plus an empirical `0.25·font`
  lift, leaving every hand-aligned label ~9 px left and 6.5 px below its
  applet position. Imported, non-auto-placed point labels without an explicit
  element/overlay/defaults `label_anchor` now take a GGB-faithful path: base
  `(4, 2·pointSize_raw)/ptUnit_ggb`, left-edge/baseline anchoring with a
  per-label baseline-depth correction (measured against a `.` probe glyph in
  the same LaTeX run, cached), no descender fudge, and the aesthetic
  `rendering.label_anchor` is bypassed. A label never dragged in GGB now
  also sits up-right of its point like the applet, instead of centred above
  it. Auto-placed labels and non-GGB scenes are unchanged.
  Known follow-up: the TikZ/JSXGraph exporters still use the old label
  semantics for these labels.

- **Manual labels keep their visual gap to the point when the font size
  changes (size-invariant anchoring).** GGB anchors a label at its
  left/baseline corner, so at a non-native font size the glyphs grow up-right —
  TOWARD the point for a label dragged left/below (В at 48px font swallowed
  its point entirely). A manual label is now anchored by the PROJECTION of
  its point onto the label's native (applet-size) bbox: the box's nearest
  face/corner is pinned, so the gap is preserved exactly for every direction
  around the point, and the label grows away from it. The projection onto a
  convex box is 1-Lipschitz, so the anchor is a continuous function of the
  offset — an animated offset (even one passing straight through the point)
  moves the label without jumps, with no sector quantisation or hysteresis.
  At the native font the scheme reduces to the exact applet placement, so
  GGB fidelity is untouched. Guarded by an all-8-directions gap test and a
  two-resolution continuity test (halving the animation step must halve the
  largest per-step movement — a genuine jump would not shrink).

- **Manual offsets keep their proportion to the glyphs at any render
  density.** In GGB both the label glyphs and the labelOffset are screen px,
  so their ratio survives any zoom. The GGB-faithful path initially divided
  offsets by ``ptUnit_ggb`` (figure space) while the font divides by
  ``ptUnit_style`` (reference-canvas px): at low reference density (e.g. a
  preview canvas fitting an 1160px view into 480px) offsets
  shrank ×2.4 while glyphs did not, and labels sat on their points. Manual
  offsets (and the GGB base) now divide by ``ptUnit_style`` — the same pixel
  space as the font, matching how every other decoration px is imported.

- **Auto-placement respects the manual side of a point label** (TZ §5.3).
  Three defects made a hand-placed label end up on the opposite side of its
  point when auto-placement was on:
  - an **arc/sector registered its FULL circle as an obstacle** («treat as
    full circle for simplicity» — and `Arc`/`CircleSector` subclass `Circle`,
    so the dedicated branch was unreachable): the phantom part of the circle
    blocked visibly-empty space, and the solid-circle rescue kicked labels
    across. Arcs now register as a polyline over their actual angular span
    (sectors also add their two radii edges);
  - **re-runs lost the user's intent**: the second placement pass (the web
    loads a scene twice for its rendered-bounds auto-config) saw only the
    first pass's `_auto_placed` offsets and re-solved from scratch. The
    respect pass now recovers the original applet offset from `ggb_raw`, so
    placement is idempotent;
  - **`_recompact_pass` rotated respected labels** up to its 40° cone while
    pulling them in. Labels pinned to a manual position now compact
    radially only.
  Plus: the sector-inference model now includes the GGB base
  `(4, 2·pointSize)` for substantive imported offsets (matches the part-1
  renderer), and gap-centring keeps the USER'S direction when the free gap
  exceeds 270° (an arc terminus / near-endpoint has no meaningful "middle";
  240°-corner centring — scene4 — is unchanged). Side effect: the
  point→label gap at zero distance is now near-uniform (spread 6 px → 2 px,
  TZ §6.4). Remaining §5.1 nuance: a descender's tail (Д, Щ) still counts
  into the bbox when a label sits North of its point.

## [1.6.4] - 2026-07-28

### Fixed

- **GIF export no longer scrambles colours (yellow/green artifacts).** manim
  0.19–0.21 builds GIFs through a `palettegen`/`paletteuse` filter graph —
  pal8 frames carrying an adaptive 256-colour palette — but declares the
  output stream as `pix_fmt "rgb8"`, a *fixed* 3-3-2 RGB grid, so the
  adaptive palette was discarded at encode time: dark blue rendered as pure
  yellow, fills broke into green/yellow dithered patches.
  `render_config.install_gif_palette_fix()` (installed automatically by
  `AnimaGeoScene.__init__`) wraps `SceneFileWriter.combine_files` so gif
  output streams keep `pal8`. Measured on a real animated scene vs the MP4
  render: mean per-pixel error 6.0 → 0.54 (of 255), p99 85 → 2, ~40 000
  hue-shifted pixels per frame → ~0, file size ~4× smaller. Transparent GIFs
  (already pal8) and all non-GIF renders are byte-unchanged; the wrap is a
  no-op on manim versions that stop assigning `rgb8`.

## [1.6.3] - 2026-07-25

### Fixed

- **Cyrillic labels no longer break rendering.** Two root causes fixed (see
  `docs/gotchas.md`):
  - `create_label` passed `tex_template=RusTex` via `.set(...)` **after** the
    `Tex` constructor, so the label was actually compiled under manim's stock
    (non-Cyrillic) template. Any visible Cyrillic label (e.g. a point named `Б`)
    raised `LaTeX Error: Unicode character … not set up` and the whole element
    (marker + label) was dropped. `tex_template` is now passed to the
    constructor, and a Cyrillic-capable template (`RusTex`) is installed as the
    global default once per scene via `ui.install_cyrillic_tex_template()`
    (`config["tex_template"]`, not `set_default` — no partialmethod recursion
    leak).
  - **Cyrillic in math mode compiled to nothing.** `$Б$` under `T2A` produced
    an empty box (the math alphabet has no Cyrillic glyphs); `$Б_1$` drew a lone
    `1`, and text like `$БВ$` lost a chunk. Cyrillic runs inside `$…$` are now
    moved to text mode via `geo.lib_elements.textify_cyrillic`
    (`$Б$` → `$\text{Б}$`, braced under sub/superscripts), applied in
    `correctedLabel`, `_render_text`, `ShowText`, and the TikZ exporter.
- **Label-compile failures degrade gracefully.** `ui._compile_label_tex` now
  falls back LaTeX → escaped plain-text → no-label instead of dropping the whole
  element; `label_placement._measure_label_bbox` estimates the bbox when a label
  can't be typeset, so auto-placement never aborts the render.

### Notes

- Latin/Greek/math labels are byte-for-byte unchanged. Labels with `\frac`,
  `\angle`, `\triangle`, etc. now typeset under `RusTex` (as free texts and
  value labels already did), fixing a small bbox mismatch with auto-placement.
- JSXGraph export is unaffected (MathJax renders math-mode Cyrillic natively).

## [1.6.2] - 2026-07-14

### Added

- **Native element prominence** (`content.prominence`) — a single decoration-size
  multiplier applied at render time. The layout, crop and label placement are
  computed at nominal prominence (1.0) and stay unaffected; prominence only
  scales the density that decoration sizes (points/strokes/labels/markers) are
  resolved against. Enables a prominence ("decoration size") UI control that never re-frames the drawing.
- **Frame-independent decoration density** (`content.decoration_scale_source`):
  - `frame` (default) — `ptUnit_style` tracks the actual export crop; `fitView`
    relies on this for two-pass convergence.
  - `reference` — re-base `rendered_bounds` density on the style reference over
    the full source view, so decoration prominence stays constant across framing choices.
  - `output` — anchor decoration size to the geometry's export zoom, so
    point/stroke/label pixels are a fixed output size set only by prominence;
    reframing or resizing the view rescales geometry alone.
  - `ggb` — GeoGebra-like: decorations keep their relative applet size and
    scale uniformly with the output canvas (not with the crop);
    `decoration_px = authored_px × (output_width / ggb_view_width) × prominence`.
- **Label-excluding crop** (`content.label_bounds='exclude'`) for
  `rendered_bounds` — crop to the geometry only, ignoring outward-placed labels.
  Default `reserve` keeps edge labels from clipping (unchanged behaviour).

### Fixed

- `apply_ggb_font_size` now `setdefault`s the global GeoGebra font onto imported
  elements instead of overwriting each element's faithful per-element font, so
  label size no longer flips with the `content.source` framing mode.

All additions are opt-in; library defaults (`fitView`, `frame`/`reference`) are
unchanged. Full suite: 1924 passed, 2 skipped.

## [1.6.1] - 2026-07-07

### Added

- `content.bounds` for `source: "rendered_bounds"` exports, allowing callers to
  provide an explicit source-pixel crop rectangle without re-measuring mobjects.
- Free GeoGebra text objects are now independent inputs in construction
  summaries/keyframes and JSXGraph specs; their positions can be animated and
  restored through the web runtime state bridge.
- Archived label-placement feedback comparison fixtures for regression work.

### Fixed

- GeoGebra `pointStyle` codes `4` and `5` now import as a rotated diamond
  (`point_shape: "diamond"`) instead of an unrotated square, matching
  GeoGebra's `POINT_STYLE_FILLED_DIAMOND` / `POINT_STYLE_EMPTY_DIAMOND`.
- `addAllGeometry()` now includes text elements in the render pass.

## [1.6.0] - 2026-07-06

### Added

- Public keyframe animation reference (`docs/keyframes.md`) and updated
  README/API/quickstart/export documentation for the v2 timeline format:
  style tracks, absolute visibility maps with entrance/exit effects, full
  easing set, dependency-order construction reveal, camera keyframes,
  emphasis events, and static playhead previews.

- New GeoGebra-compatible commands: `Tangent(line, conic)` / `Tangent(P, func)`
  / `Tangent(c1, c2)` (tangents parallel to a line; tangent to `y=f(x)` at
  `x(P)`; common tangents of two circles), `Trilinear(A, B, C, x, y, z)`,
  `Dilate(obj, k, O)` (homothety), `ClosestPoint(path, P)`, `Slope(line)`, and
  the vector helpers `Direction(line)`, `UnitVector(v)`,
  `PerpendicularVector(v)`, `Dot(u, v)`, `Cross(u, v)`.

- Keyframe easing grew from 5 to the full 17-name set (`smootherstep`, sine
  in/out/in_out, cubic in/out/in_out, `rush_into`/`rush_from`,
  `ease_out_back`, `ease_out_elastic`, `ease_out_bounce`), a lossless port of
  the web frontend's `applyEasingValue` — the same `"easing"` name renders
  identically in the web preview and the exported video.
- `AnimaGeoScene.get_element_states()` — a read-only per-element snapshot
  `{name: {type, visible, style}}` (every non-axis element's type, current
  visibility, and resolved animatable style values), symmetric to
  `get_independent_elements()`, for the web keyframe-state inspector and
  diffs.
- Keyframes v2 (`"version": 2`): per-keyframe `styles` maps animate element
  styles between keyframes — colors (Oklab-interpolated; `rendering.
  color_interpolation: "srgb"` opt-out), opacities, pixel sizes,
  `label_offset_px`, discrete props (snap at mid-transition), `null` = revert
  to pre-animation style. Styles may target any element. v1 keyframe JSON
  still plays byte-identical but is deprecated (DeprecationWarning).
- `updateGeoElements` now carries `z_index` through `become()` so z-order
  changes take effect without a remove/add cycle.
- Keyframes v2: per-keyframe `visible` maps (absolute `{name: bool}`; `show`/
  `hide` arrays are v2 sugar that fold into it) animate element
  appearance/disappearance with entrance/exit effects — enter: `fade`
  (default), `none`, `create` (progressive stroke draw), `grow` (scale from
  center); exit: `fade` (default), `none`, `uncreate`, `shrink`. Effects are
  set per-keyframe via `enter`/`exit` maps (`{name: {effect, duration, at}}`
  or a bare effect string), with optional top-level `defaults` for
  `easing`/`enter`/`exit`.
- Keyframes v2 plays show/hide at exact interval duration — the legacy extra
  0.4s injected per show/hide batch in v1 is dropped. v1 keeps the injected
  0.4s (unchanged, deprecated).
- `AnimaGeoScene.reveal_construction(lag, duration, effect, play)` — a macro
  that stages a dependency-ordered, staggered reveal of the whole
  construction, picking a sensible per-type entrance effect (points fade,
  lines/circles/curves `create`, text/labels `write`) unless a single
  `effect` is forced; returns the generated v2 keyframes and plays them
  unless `play=False`.
- `label_text` is now an animatable style key in keyframes v2 `styles` —
  a discrete swap at mid-transition (like `label_visible`), not a
  cross-fade or glyph-by-glyph morph.
- `write` entrance effect: progressive glyph reveal for text/labels, usable
  per-keyframe (`enter: {name: "write"}`) and in top-level `defaults.enter`.
- Keyframe `keyframe_snapshots` label-placement pre-pass is now style-aware:
  it applies each keyframe's `styles` (font/arc size, `label_visible`, …)
  before measuring label bboxes, so label layouts stay correct for keyframes
  that animate those properties.
- Keyframes v2: `"@camera"` reserved pseudo-element in `values` animates the
  viewport (`{"center": [x, y], "width": w}`) — a cinematic pan/zoom of
  `camera.frame` where geometry and pixel-sized decorations scale together
  with the zoom, unlike GeoGebra's pixel-invariant `ZoomIn`.
- `AnimaGeoScene.apply_keyframes_at(keyframes_data, t)` — statically places
  the scene at playhead time `t` (no animation), for a single-frame preview
  (e.g. followed by `exportSVG`). Idempotent.
- Keyframes v2: per-keyframe `"events"` play one-shot, self-restoring
  emphasis on one or more targets — `indicate` (scale+colour pulse),
  `flash` (radial flash lines), `circumscribe` (temporary box around the
  target). Each event is `{effect, targets, at, duration, color?, scale?}`,
  timed within the keyframe interval; the scene returns to its prior state
  once the event completes. `passing_flash` is not available yet.

### Changed

- **Background resolution now honours the GeoGebra background as an opt-in
  secondary source.** Priority: explicit style background → parsed GeoGebra
  `<bgColor>` → white. Clearing a style's background (no concrete
  `presets.color.background` / `rendering.background`) lets the construction's
  own GeoGebra background show through instead of forcing white. The effective
  colour is mirrored into `presets.color.background` so fills follow it.

### Fixed

- GeoGebra function expressions are now imported when the `<expression>` omits
  `type="function"` but the companion `<element>` carries it. Function
  expressions may reference numeric sliders/angles/booleans from the same
  construction; those parameters are substituted before sampling.
- GeoGebra `If(...)` function expressions produced by the XML converter now
  parse as SymPy `Piecewise`, matching the existing `If[...]` support and
  preventing piecewise functions from failing during rendering/export.

## [1.5.0] - 2026-07-04

### Changed

- **Relicensed MIT → Apache-2.0** as part of the initial public source release
  (`LICENSE` + `NOTICE`; `pyproject.toml` `license = "Apache-2.0"`). All
  releases from 1.5.0 on are Apache-2.0; 1.0.0–1.4.6 were published under MIT.

### Added

- **First-class GeoGebra text objects across the whole pipeline** — parse,
  render (SVG/MP4), and export (TikZ, JSXGraph). Supports static text, LaTeX
  text, and dynamic text that resolves live values (`Point → (x, y)`,
  `Polygon → area`, `Segment → length`, numbers/angles/booleans with
  trailing-zero stripping). Previously LaTeX text was dropped and plain text
  was unrenderable.
  - `Text` element with position/anchor and `is_latex`; manim-free value
    formatting shared by the renderer and exporters.
  - GGB parser splits string-literal expressions into literal/object segments,
    with `<startPoint>` anchoring, `<isLaTeX>`, `<font>`, and kernel decimals.
  - `_render_text` (top-left anchor, live dynamic resolution), TikZ `\node`,
    and a JSXGraph text creator + `animageo-board/v1` spec element.

## [1.4.6] - 2026-07-04

### Changed

- Updated the packaged AI usage guide with stronger autonomous-animation
  defaults: prefer native AnimaGeo marks over manual Manim overlays, reveal
  polygons as single drawable objects when that is the intended construction,
  enable automatic label placement for labeled staged animations, and verify
  label placement before the first motion frame.

### Fixed

- **`autoPlaceLabels(dynamic=True)` now synchronizes labels during visibility
  transitions.** `Show`/`playShow`, `Hide`/`playHide`, and
  `setVisible(update=True)` recompute the current visible label layout and seed
  the dynamic tracker before the next mobject/render frame, so staged labels
  appear in solved positions immediately instead of correcting only when the
  first `addUpdater`/`updateVar` animation starts.
- **Indexed conic intersections now use GeoGebra-style known-point ordering.**
  `Intersect(conic, line, 2)` and related indexed conic intersections now share
  the same known-point ordering contract previously applied to circle
  intersections, avoiding selection of the already-known point when GeoGebra's
  second intersection is requested.

## [1.4.5] - 2026-07-03

### Added

- **AI agent usage guide shipped in the package** (`animageo/AI_USAGE_PROMPT.md`,
  rewritten as a self-sufficient reference). Written for an AI agent with zero
  prior knowledge of animageo: environment setup, canonical static-SVG and
  MP4-animation script skeletons, the two-pass `fit_view` viewport recipe for
  DSL-built scenes, verified DSL factory signatures, construction-correctness
  rules, marks/labels/value-labels, style JSON, staged reveal + animated
  variables + keyframes, a visual verification protocol, and a troubleshooting
  table. Validated end-to-end by independent context-free AI agents (six
  scenarios: nine-point circle animation, incircle figure, parabola definition
  animation, tangents from external point, parallelogram diagonals, inscribed
  angle theorem). The wheel now includes `animageo/*.md` (MANIFEST.in +
  package-data).
- `animageo --ai-guide` / `python -m animageo --ai-guide` — print the packaged
  AI usage guide and exit (no `.ggb` argument needed); README gained an
  "AI agent usage" section pointing agents at it.
- **`AnimaGeoScene.fitView(width, height, *, padding=40, style=None,
  passes=2)`** — canonical framing for DSL-built scenes (which have no
  meaningful default viewport). Measures the rendered bounds of the visible
  elements and configures the reference→content→export layout so the content
  fills the canvas with a uniform pixel margin; runs two
  `applyStyle(content='rendered_bounds')` + `updateAllGeometry()` passes (the
  first fixes the pixel-style scale, the second re-measures with correctly
  sized points/labels). Keeps the scene's current style when `style=` is
  omitted. Replaces the hand-rolled double-`applyStyle` recipe from the AI
  guide.

### Fixed

- **`Point(Polygon)` is now imported instead of dropped.** A GeoGebra point
  constrained to a polygon boundary had no dispatch (`point_P` was missing), so
  the point built as `None`, cascaded every dependent segment to
  `depends_on_unsupported`, and recorded a spurious `unsupported_signature`
  diagnostic (a hard failure under `--strict`). Added the `point_P` creator and
  taught the parser to recognise `Polygon` as a point host: the point is now
  materialised at its serialized coordinates (a fixed point — no perimeter
  `tparam` yet) so it renders and unblocks its segments. Also fixed a latent
  bug where the parser's point-element handler appended a duplicate `Element`
  instead of overwriting an already-created output.
- **Transparent GeoGebra arcs/sectors (`type="conicpart"`) no longer render
  filled.** `conicpart` was missing from the fill-import type list, so a
  `CircleArc` with `<objColor alpha="0">` never wrote `fill_opacity` into
  `ggb_style`; the resolver then fell back to the builtin `arc` default
  (`fill_opacity = 1`) and drew an opaque fill. `conicpart` is now honoured in
  both import paths (`ggb_parser` and `ggb_resolver`), so the arc's real alpha
  wins.
- `applyStyle(reference={'size': [w, h]})` — the documented list/tuple form of
  the reference size was silently ignored (only the
  `{'width': ..., 'height': ...}` dict form worked), so pixel styles resolved
  against a degenerate `ptUnit_style` and DSL-only scenes rendered with giant
  points/labels. Both forms now behave identically.
- Style validation no longer warns about underscore-prefixed top-level keys
  (`_comment` etc. are comments by convention — the shipped `builtin.json`
  itself uses one), and `applyStyle` logs a dict style's `name` instead of
  dumping the whole style dict into the INFO log.

## [1.4.4] - 2026-07-03

### Added

- **Points on conics, loci and function graphs are now fully animatable in
  keyframes.** A `tparam_point` on an ellipse/hyperbola/parabola/circle-as-conic,
  a locus, or a function graph can be driven through `play_keyframes` the same
  way circle/segment/line points already were. `get_independents()` reports the
  path type in the new `constraint` field (`circle`/`segment`/`ray`/`line`/
  `ellipse`/`hyperbola`/`parabola`/`locus`/`function`); ellipse and circle
  interpolate cyclically with 2π wrap (shortest arc), hyperbola carries a
  `(branch, t)` pair (branch snaps at t=0.5), everything else is linear.
- **Keyframe values for `tparam_point`s may be plain `[x, y]` coordinates** in
  addition to `{"tparam": ...}` — the library projects them onto the point's
  path via the new public API `Construction.tparam_from_coords(name, coords)`.
- `animageo/geo/tparam.py`: new module unifying point↔path-parameter math
  (`tparam_from_point_and_path` dispatcher, `get_tparam_from_point_and_function`
  for function graphs); the classic circle/line/segment/conic/locus helpers
  moved here from `ggb_parser`, which now re-exports them for compatibility.
- `point_F` command — a point constrained to a function graph; GGB `Point[f]`
  now imports with a `tparam`.

### Changed

- **Locus point parameter now uses nearest-segment projection** (with
  fractional position along the segment), matching GeoGebra's
  `GeoLocus.pointChanged` semantics, instead of snapping to the nearest sampled
  vertex.

### Fixed

- **RecursionError after ~1000 renders in one process (labels and points
  silently vanishing).** `applyStyle` (via `setStyle`) called
  `Text/MathTex/MarkupText.set_default(color=…)` on every invocation; manim's
  `set_default` wraps the
  current `__init__` in a new `functools.partialmethod` each time (nested
  partialmethods never flatten because the class attribute read returns the
  descriptor's compiled `_method` function), so the chain grew by one layer
  per render. Once it exceeded `sys.getrecursionlimit()`, every label
  construction raised `RecursionError`: per-element error recovery silently
  dropped points and labels, `autoPlaceLabels` crashed on Tex bbox
  measurement, and DecimalNumber-backed value labels failed too. The
  `set_default` calls are removed: the label render path always passes its
  colour explicitly (`col_label`), and `ShowText` now receives explicit
  colours too. `setStyle` no longer mutates any global manim class state,
  which also makes concurrent renders in threads safe from racing on
  `MathTex.__init__`.
- **Cyclic GGB macros no longer crash `loadGGB` with RecursionError.**
  `expand_macros_in_construction` recursed once per expansion pass with no
  bound, so a `geogebra_macro.xml` whose macro body calls itself (directly
  or mutually) blew the stack after ~1000 passes. Expansion now stops after
  32 passes with a warning; the unexpanded calls surface through the
  existing unsupported-command diagnostics.
- **RecursionError render failures now log a root-cause hint.** A
  `RecursionError` caught by the per-element recovery in `CreateMObject` is
  process-wide state corruption, not an element defect; the warning now says
  so instead of reading like a per-element failure.

## [1.4.3] - 2026-06-30

### Fixed

- **Angle markers are now obstacles for automatic label placement.** A vertex
  point's label could be placed in the sector occupied by its angle marker (a
  right-angle square or arc), leaving the marker between the label and its
  point. The new opt-in `overlay.label_placement.angle_marker_obstacle` flag
  (default `false` → byte-identical GGB import) registers the *real* drawn
  marker at its rendered pixel radius as an obstacle (mirroring `_render_angle`
  via `_angle_drawn_sector` / `_angle_marker_obstacle_segments`, replacing the
  legacy coarse `0.3·min(arm)` arc) and excludes the marked wedge from the
  point-label direction resolvers (`_bisector_of_largest_gap`,
  `_bisector_of_gap_nearest`), so a GGB offset hint can no longer pin a label
  onto the marker. Enabled in the recommended label-placement preset.

## [1.4.2] - 2026-06-27

### Fixed

- **Stable Manim layer order during MP4 animation.** Equal z-index tiers now get
  a tiny construction-order tie-breaker before being passed to Manim. This keeps
  polygon stroke overlays and ordinary segments in the same relative order after
  `Polygon` objects are recreated via remove/add during `updateGeoElements()`.

### Documentation

- Documented the z-index tie-breaker and the `Polygon` remove/add layer-order
  contract in the style guide and gotchas.

## [1.4.1] - 2026-06-27

### Fixed

- **GeoGebra-style ordering for multi-output intersections.** Multi-output
  `Intersect(circle, ...)` now uses the same already-known-point ordering as
  indexed `Intersect(..., index=1/2)`, so `.ggb` imports keep GeoGebra's output
  label mapping when one intersection coincides with a point used to construct
  the input objects. This fixes dependent constructions such as circles through
  a named second intersection being built through the wrong point.

### Documentation

- Documented the public intersection-ordering contract: tuple-unpack order,
  indexed `Intersect(..., index=N)`, `.ggb` import, and export/JSXGraph paths
  must agree; `index` remains 1-based.

## [1.4.0] - 2026-06-23

### Added

- **Comprehensive automatic label placement** (`autoPlaceLabels()` /
  `compute_label_layout` / `apply_label_layout`). A deterministic greedy solver
  with continuous (non-octant) direction search, then a sequence of opt-in
  refinement passes, all configured under `overlay.label_placement`. Every flag
  defaults OFF so a bare GGB import stays byte-identical; enable the documented
  **recommended preset** (see `docs/styles.md`) for the validated layout. Key
  mechanisms:
  - **Visual-glyph-box reasoning** — a vertex label's sector is chosen from where
    its text actually renders (anchor corner + descender), not the raw offset
    vector, so it keeps the user's original part of the angle.
  - **Compaction + association (`compact_labels`, `overlap_tol_px`)** — pulls a
    label that overshot a dense node back next to its point, accepting a small
    clip of a SOLID line *incident to its own point* rather than a far
    displacement; never moves it past the Voronoi midpoint to another point
    (no false attachment). Dashed lines/circles and angle markers stay hard.
  - **Solid-circle rescue** — a label stuck on a solid circle is moved to the
    nearest clear spot (e.g. radially outward).
  - **Anti-hug** — a label clinging to a line in a *sparse* spot is nudged out
    for clearance, bounded by a small cap and the association limit.
  - **Point-on-circle radial placement** — a point on a solid circle takes the
    symmetric radially-outward direction.
  - **Region-aware cluster consistency** — a collinear row/column of free points
    aligns to one side, with blocked members nudged out so the run reads uniform.
  - **Contrast-aware label colour**, **viewport clamp**, **declutter**,
    **dashed-vs-solid overlap weighting**, and **per-frame / keyframe dynamic
    trackers** (EMA + anchor hysteresis) for animation.
  - Obstacles are culled to each label's reach, keeping dense scenes fast.
- **Leader lines (P2-A, opt-in, `label_overflow: "leader"`)** — a genuinely
  stuck POINT label is displaced to a free spot with a thin connector, rendered
  in SVG/manim, TikZ and the eval-free JSXGraph spec. Default `"overplot"` (off).
- **Label-name canonicalization** — primed names (`U'''`) recovered from the GGB
  `name_mapping` for display.

### Notes

- The auto-placement passes are static-layout only and do not change default
  (un-`enabled`) GGB import. Known limit: two *equal adjacent* angles still get
  ambiguous value labels (both show the same measure).

## [1.3.4] - 2026-06-19

### Fixed

- **`content.padding` is now a uniform canvas-edge margin**, not a source-crop
  inset. It previously expanded the `rendered_bounds` source view (an inward
  crop margin that scaled the whole figure in source px and did nothing for
  other sources). Now it fits the content into the export canvas reduced by
  `padding` on every side and insets it by `padding` — an exact margin in
  output pixels, applied at the reference→export stage for all content sources.
  `rendered_bounds` crops tight again. Exposed to UIs as a padding control.

## [1.3.3] - 2026-06-18

### Fixed

- **Angle labels no longer fly far off very small angles.** The narrow-angle
  clearance in `compute_angle_label_center` pushed the label out by
  `clearance / sin(half_angle)`, which blows up as the angle → 0 — so a
  value-label on a shrinking angle (e.g. during an animation) drifted far from
  the marker. The push is now capped at `base_dist * 2.5`
  (`ANGLE_LABEL_NARROW_MAX_FACTOR`), keeping the label a reasonable distance
  from the vertex (it may then slightly overlap the near-parallel sides, which
  is preferable to flying away). Wide angles are unchanged.

## [1.3.2] - 2026-06-18

### Fixed

- **Right-angle labels no longer drift away from their marker during
  auto-placement.** `compute_label_layout` targeted a right angle's label at the
  non-right arc radius (`arc_size_px`), while the square right-angle marker is
  sized from `right_angle_size_px`. When those differed (or auto-radius enlarged
  the arc), the label floated out to the phantom arc distance, detached from the
  smaller square. The label target now follows the actual square marker's outer
  corner (`right_angle_size_px`). No change when
  `right_angle_size_px == arc_size_px`.

### Added

- **`fill: "stroke"` — fill follows the element's own outline colour.** The style
  resolver now treats the literal fill value `"stroke"` as "use this element's
  resolved stroke colour", so a shape can be filled with a translucent tint of its
  own border (opacity set separately) rather than a fixed palette slot — e.g. a
  blue-outlined polygon gets a blue wash, not a reddish `accent_light`. Resolved
  centrally in the style resolver, so the manim renderer and the TikZ/JSXGraph
  exporters stay consistent. Explicit/literal fill colours are unaffected.

## [1.3.1] - 2026-06-13

### Fixed

- **`rendered_bounds` no longer clips auto-placed edge/corner labels.** When
  `content.source="rendered_bounds"` (the tight fit-to-content crop) was combined
  with label auto-placement (`overlay.label_placement.enabled`), labels of points
  at the extreme edges of the figure were clipped off the export canvas. The crop
  was measured inside `applyStyle` *before* `autoPlaceLabels()` shifted labels
  outward, so the frozen canvas had no room for them. `applyStyle` now re-fits the
  rendered-bounds crop *after* placement (a second measurement pass that picks up
  the placed offsets), so the canvas always contains the labels. Other content
  sources (`ggb_view`, `source_view`) and placement-disabled styles are unchanged.

## [1.3.0] - 2026-06-01

### Added

- **Fast value labels (DecimalNumber-backed).** Labels that display a changing
  numeric value (`label_mode` `value`/`label_value`: angle measure, segment
  length, vector norm, circle radius, polygon area, measure) now animate via a
  new `ui.ValueLabel` (manim `DecimalNumber` with cached digit glyphs) instead
  of recompiling a `Tex` every frame — ~80× faster per value label (~130–280 ms
  of LaTeX per frame → ~2 ms). `labels.resolve_label_spec()` exposes the
  structured prefix/value/suffix; `ValueLabel` is also exported from the package
  for hand-built live read-outs. Static SVG/PDF/TikZ export keeps the `Tex` path
  (trailing-zero stripping, byte-identical output); the fast path engages only
  while animating (`play_keyframes`, `addUpdater`/`animating`). Master switch
  `rendering.fast_value_labels` (default `true`).
- **Framework-agnostic web integration** for controllable, movable geometry
  figures — embeddable in any web project (React/Vue/Svelte/vanilla/no-build),
  not just a standalone HTML page.
  - **Declarative board spec** `exportJSXGraph(output="spec")` →
    `animageo-board/v1`: eval-free structured JSON (elements with semantic kind +
    engine render-instruction + structured parents; an interactive-input schema;
    coverage). No JS strings. JSON Schema shipped in the wheel at
    `animageo/exporters/jsxgraph/board.schema.json` and loadable via
    `animageo.exporters.jsxgraph.load_schema()`; real exports are validated
    against it in the test suite. CLI: `-o board.json --format jsxgraph`.
  - `Construction.get_independents()` now surfaces optional slider `min`/`max`/
    `step` (from a var's style), feeding the spec's input schema.
  - **`web/runtime`** (`@animageo/runtime`): headless `createBoard(spec,
    container, opts) -> BoardHandle` with construction-relative **signals**
    (`ready`/`change`/`commit`/`viewchange`/`error`) and **actions**
    (`getState`/`setState`/`setValue`/`reset`/…). JSXGraph is injected (peer
    dep); no globals; multi-instance safe.
  - **`web/web-component`** (`<animageo-board>`): the zero-framework primitive —
    signals as `CustomEvent`s, actions as element methods.
  - **`web/adapters/`**: thin React / Vue / Svelte / vanilla templates.
  - Tests: `tests/test_jsxgraph_spec.py` (Python) + `node --test` in each web
    package, including a cross-language contract test against real exported specs.
  - Verified end-to-end with a real headless-Chrome smoke against live JSXGraph
    (`web/runtime/scripts/browser-smoke/run.mjs`): a real exported spec builds,
    `setState` moves a point, `change`/`commit` fire on real drag events, and the
    SVG renders.

- **TikZ export** (`scene.exportTikZ(...)`): comprehensive, semantic TikZ output
  for inclusion in LaTeX documents — the TikZ counterpart of `exportSVG`. Emits
  native primitives (`\draw circle`/`ellipse`/`(a)--(b)`/`arc`/`[->]`), real
  LaTeX `\node` labels, and `\draw plot coordinates` for sampled curves
  (parabola/hyperbola/function/implicit/locus). All drawable types are covered,
  reading the same style resolver as the renderer (GGB import → overlay →
  explicit `elem.style`): colours (interned into `\definecolor`), opacities,
  dash patterns, line caps, tick marks, angle-arc auto-sizing, point shapes and
  z-order. Coordinates are math units; the picture's `x=/y=` unit reproduces the
  SVG physical size while markers/widths/fonts use absolute `pt`.
  - Snippet output by default (for `\input{}`); `standalone=True` wraps a
    compilable `\documentclass{standalone}` document with a Cyrillic-ready
    preamble.
  - CLI: `-o foo.tex` (format inferred), `--format tikz`, `--standalone`.
  - New package `animageo/exporters/tikz/`; docs in `docs/tikz_export.md`.
  - Verified end-to-end: every drawable type and every `TikZOptions` setting are
    covered in `tests/test_tikz_export.py`, including `pdflatex` compile smoke
    tests (skipped when no LaTeX toolchain is available).

- **PDF / EPS export** (`scene.exportPDF(...)`, `scene.exportEPS(...)`): vector
  output on the existing Cairo path (the same mobject walk as `exportSVG`).
  `dpi` (default 96, matching the TikZ exporter) controls the physical page
  size; the figure stays vector and rescales via `\includegraphics[width=...]`.
  EPS warns once when the scene has semi-transparent fills/strokes (EPS has no
  transparency — cairo flattens them; PDF/SVG preserve opacity).
  - CLI: `-o foo.pdf` / `-o foo.eps` (format inferred) or `--format pdf|eps`,
    with `--dpi`.
  - Internals: `parsers/svg_parser._get_cairo_context(surface=…, dpi=…)` now
    builds SVG/PDF/PS/EPS cairo surfaces; `exportSVG/PDF/EPS` share
    `_export_cairo`. Tests in `tests/test_pdf_eps_export.py`.

- **Animation containers GIF / WebM / MOV** (in addition to MP4) via the manim
  renderer. `animageo.configure_render(format=…, fps=…, transparent=…)` selects
  the container before a render.
  - CLI render track: `--format png|gif|mp4|webm|mov` (inferred from `-o`),
    `--keyframes file.json` to animate, plus `--fps` / `--transparent` /
    `--quality {l,m,h,p,k}`. The produced file is moved to the requested `-o`
    path.
  - CLI now propagates `PYTHONPATH` to the `manim` subprocess so the generated
    driver imports `animageo` when running from a source checkout (not only when
    pip-installed). Tests in `tests/test_render_config.py`,
    `tests/test_cli_main.py`.

- **Interactive JSXGraph export (Phase 1)** (`scene.exportJSXGraph(...)`): a
  live, draggable construction in the browser. Unlike the SVG/PDF/TikZ
  exporters, which serialise a rendered frame, this *transpiles the construction
  graph*: free points → draggable points, points-on-curves → gliders, numbers →
  sliders, booleans → checkboxes, and derived elements are created in terms of
  their parents so JSXGraph recomputes them live on drag.
  - Live creators: midpoint/center, segment, line (+parallel), ray, vector,
    circle (center+point / +radius / +slider-driven radius), semicircle,
    **polygon** (named edges bound to `poly.borders[i]`, so the shape and
    everything built on its edges tracks drags), perpendicular,
    perpendicular-bisector (composite), angular bisector, angle, **ellipse /
    hyperbola / parabola / conic (5-point)**, reflection/mirror, and
    intersection (indexed; *smart* — live only when both parents are line/conic
    objects, otherwise placed at the computed coordinates).
  - Everything else is **drawn statically**: functions, implicit curves,
    conics-by-expression, arcs, sectors and loci are sampled into JSXGraph
    `curve` elements (level-0 directly-defined curves are emitted before their
    dependents). Only genuinely-empty (`None`) outputs are skipped; a
    **coverage report** lists live vs static (logged at INFO).
  - Verified in a real browser (headless Chrome) on `ex_general.ggb`
    (17 live / 0 static) and `func5.ggb` (conics/functions/implicit all drawn):
    renders, MathJax labels typeset, no JS errors, dragging a free point
    recomputes dependents live.
  - Live **transforms**: `rotate` / `translate` of points and of segments /
    lines / circles / vectors / polygons via a JSXGraph `transform` object
    (dragging the source moves the image). Live **Tier-V numeric values**: a
    derived number feeding a creator — e.g. `Circle(M, Distance(A,B))` — becomes
    a live JS function (`distance`/`length`/`radius` +
    `add/sub/mult/div/pow/abs/sqrt/sin/cos/tan`). `tangent`-from-a-point is
    drawn statically (single-output / branch-ambiguity — see the plan doc).
  - Output flavours: `html` (default), `js`, `json`, and `moodle`
    (`<jsxgraph>` block for the filter_jsxgraph plugin, best-effort).
  - Output `html` (self-contained, default — CDN JSXGraph `1.10.1` + MathJax 3
    labels), `js` (board fragment), or `json` (board spec).
  - CLI: `-o foo.html` (format inferred) or `--format jsxgraph`.
  - **Visibility fidelity:** hidden elements are emitted with `visible: false`
    (kept in the board so visible dependents still recompute on drag) instead
    of being drawn — mirrors a hidden GeoGebra object still participating in the
    construction.
  - **Angle orientation fidelity:** a 3-point `Angle` now honours GeoGebra's
    reflex/non-reflex setting by emitting the dedicated `reflexangle` /
    `nonreflexangle` element (keyed off the resolved `angle_range`, same as the
    SVG renderer) instead of the plain `angle`, which always sweeps CCW
    `p1`→`p3` and so could draw the wrong side of the plane.
  - **Board chrome from the scene:** background colour, axes and grid
    show/hide, per-axis visibility, and axes/grid colours are now imported from
    the GeoGebra view (`bgColor` / `showAxes` / `showGrid` / `axesColor` /
    `gridColor`) instead of being hard-coded. `JSXGraphOptions.axis` / `grid`
    default to `None` (mirror the scene; GeoGebra defaults — axes on, grid off —
    when the scene is silent) and accept an explicit `True`/`False` override;
    `background` defaults to the scene colour, takes a CSS override, or `""` to
    let the page show through. Also imported (mirroring the SVG renderer):
    grid boldness (`gridIsBold` → grid stroke width), grid spacing
    (`gridDistX/Y` → `majorStep`), per-axis tick numbering (`showNumbers` →
    `drawLabels`) and tick spacing (`tickDistance` → `ticksDistance`), and the
    x/y unit scale → `keepaspectratio` (equal scales keep circles round;
    unequal scales reproduce GeoGebra's distortion; `JSXGraphOptions.keepaspectratio`
    is now `Optional` and overrides). GeoGebra polar/isometric grids have no
    JSXGraph equivalent and fall back to a rectangular grid (logged).
  - **Element size fidelity:** angle arcs carry GeoGebra's `arcSize` over to the
    JSXGraph angle `radius` (px → user units), and a deliberate `labelOffset` is
    emitted as the JSXGraph label `offset` (near-zero offsets keep JSXGraph's
    own sensible default). Stroke/fill colour, width, opacity, dash, point
    size/shape and label colour already route through the shared style resolver.
  - New package `animageo/exporters/jsxgraph/`; tests in `tests/test_jsxgraph_export.py`.

### Changed

- **Manim 0.20.1** is now the minimum supported renderer (`manim>=0.20.1,<0.22`).
- JSXGraph export: dash patterns now map to JSXGraph dash indices by the
  dash/line-width ratio (dotted → 1, dashes → 3, loose dashes → 4), mirroring
  the TikZ exporter's thresholds, instead of collapsing every dash to one style.
- JSXGraph export: the resolved z-index maps to a JSXGraph `layer` so the live
  widget stacks like the SVG/PNG renderer (fills below angles below lines below
  strokes below points), instead of relying on JSXGraph's per-type defaults.
- JSXGraph export: an explicit 9-point label anchor (from GGB import or the
  `label_placement` solver) now maps to JSXGraph `label.anchorX`/`anchorY`, so a
  label offset is applied relative to the same corner the renderer uses (most
  visibly fixes solver-placed and angle labels) instead of JSXGraph's default
  anchor.
- JSXGraph export: angle arc radius now mirrors the renderer — the resolved
  `arc_size_px` run through `compute_effective_arc_size_px` (multi-arc expansion
  for `tick_count > 1`, plus `overlay.angle_radius` auto-scaling when enabled),
  instead of the raw base radius. Byte-for-byte unchanged when `angle_radius` is
  off (the default) and `tick_count` is 1.
- JSXGraph export: **decorations now carried** — vectors get a native, live
  arrowhead sized from the resolved GGB `arrow_length_px`/`stroke_width_px`
  (`lastArrow`), and segments with `tick_count > 0` get **live congruence tick
  marks**: short perpendicular dashes at the midpoint, built from
  function-valued anchor points tied to the segment's parents (so they track
  drags — no frozen geometry). Mirrors the renderer/TikZ geometry
  (`tick_length_px`/`tick_shift_px`). None emitted when `tick_count` is unset.
  Verified on live JSXGraph (headless Chrome) incl. the GGB congruence marks in
  `ex_general.ggb`.
- JSXGraph spec: now carries `ptUnitGgb` / `ptUnitExport` (the GGB authoring and
  export px-per-unit). A live board rendering the bounding box at a different
  scale can rescale label offsets (`offset / ptUnitGgb`) and reproduce the
  absolute pixel size of pixel-sized decorations. Schema updated accordingly.
- JSXGraph export: segment congruence ticks now keep a **fixed pixel length
  under zoom** — the tick coordinate functions divide the pixel size by the
  board's live px-per-unit on every redraw (like GeoGebra), instead of baking a
  math-unit size at export time.
- JSXGraph export: closed shapes with a fill colour now always pin
  `fillOpacity` (even at 0), so a stroke-only GeoGebra circle/conic/polygon is
  not painted solid by JSXGraph's default; point `size` is kept fractional
  (no longer rounded to an int) so the point-size : line-width ratio matches the
  SVG/preview.

### Documentation

- The HTML user guide was reworked end-to-end: migrated under `docs/guide/`
  (old `docs/style_guide/` removed and links redirected), renumbered to 12
  chapters, added an outputs map and a new interactive-web chapter with a live
  board, and an expanded export/reference covering every exporter, the web spec
  and the CLI.

## [1.2.6] - 2026-05-24

### Changed

- Finalized the style/layout API cleanup around the canonical
  `style` / `reference` / `content` / `export` arguments.
- Renamed the faithful GeoGebra style mapping helper from the legacy adapter
  naming to `style.ggb_resolver.resolve_ggb_style()`.
- Style validation is now stricter: removed legacy top-level sections,
  removed visual aliases, `rendering.scale_export`, and unknown
  `import.policy` keys fail fast instead of being silently accepted.
- Overlay and label-placement documentation now describe the resolver-based
  style path directly.

### Removed

- Removed runtime compatibility shims for deprecated API arguments such as
  `style_file`, `px_size`, `reference_size`, and flat `export_*` kwargs on
  `loadGGB()` / `applyStyle()`.
- Removed the deprecated CLI `--debug` shortcut; use `--verbose` or
  `--log-level DEBUG`.
- Removed the `angle_gap_px` label-placement fallback in favor of explicit
  `angle_gap_arc_px` and `angle_gap_sides_px`.

### Tests

- Updated style/import-policy tests to assert the canonical API and removed
  legacy compatibility behavior.

## [1.2.5] - 2026-05-24

### Fixed

- GeoGebra XML parsing now accepts both the historical misspelling
  `euclidianView` and the correct `euclideanView` element emitted by current
  GeoGebra files.

## [1.2.4] - 2026-05-17

### Added

- Added a unified logging configuration helper and wired CLI verbosity flags
  through it.
- Added GeoGebra custom macro expansion before construction parsing.

### Fixed

- Unsupported command diagnostics are now summarized through structured
  logging instead of ad-hoc console output.

## [1.2.3] - 2026-05-15

### Added

- Imported GeoGebra axes/grid view settings are now preserved and can render as
  a quiet coordinate background layer.
- DSL `Intersect(...)` factories now accept `index=` as a semantic keyword for
  selecting a specific intersection.

### Changed

- `content.infinite_policy` now defaults to `ignore` for `rendered_bounds`;
  use `clip` explicitly to include `Line`/`Ray` bounds clipped by the current
  source camera.
- Style preset references now also accept short forms such as `color.main`,
  `line_width.main`, and `tick.main` where the preset group is unambiguous.
- Value-label precision now defaults to one decimal place and can be set via
  `rendering.label_value_precision`.
- Expanded API docs for the accepted `style`, `reference`, `content`, and
  `export` shapes, values, and defaults.
- Removed the PyPI `Development Status :: 5 - Production/Stable` classifier
  from package metadata.

### Fixed

- Automatic label placement now clips line/ray obstacles to the current scene
  bounds and uses exact segment/bbox clipping instead of dense sampling.

## [1.2.2] - 2026-05-09

### Added

- **Unified layout API** — `loadGGB()` and `applyStyle()` now accept
  `style`, `reference`, `content`, and `export` blocks. `style` can be a JSON
  path, raw style dict, or `StyleConfig`; `reference`, `content`, and `export`
  can be passed as dictionaries for structured runtime layout control.
- **Top-level style reference** — style JSON now uses
  `reference: {size: {width, height}, source}` as the authoring/reference
  canvas metadata.
- **Reference-to-export layout pipeline** — geometry/content placement on the
  reference canvas is separated from physical export placement, preserving
  authored visual scale while still supporting different output sizes.

### Changed

- Public examples, guide snippets, docs, style-guide generated sources, and
  bundled style JSON files now use the new `style` / `content` / `export`
  shape instead of legacy `style_file`, `px_size`, and flat `export_*` fields.
- Runtime export sizing is now expressed through
  `export={'size': {'width': ..., 'height': ...}}`; one side may still be
  `"auto"`.
- Rendered-bounds fitting is now configured as
  `content={'source': 'rendered_bounds', 'padding': ...}`.
- AI construction summaries now report viewport dimensions under
  `viewport.size` instead of `viewport.px_size`.

### Fixed

- `applyStyle(style=...)` now correctly passes the style path/dict into the
  legacy `GeoStyle` container while keeping `StyleConfig` as the canonical
  resolver source.
- Updated the guide render server and standalone style-guide example
  generator to emit runnable snippets with the new API.
- Migrated conics/functions helpers and all example style files away from
  obsolete public export/style fields.

### Tests

- Added and updated coverage for reference/export layout separation, style
  reference parsing, dict-based style loading, guide overlay examples, AI
  summary viewport metadata, label placement behavior, and migrated examples.

## [1.2.1] - 2026-05-08

### Added

- **Split export layout** — `loadGGB()` and `applyStyle()` now support
  `reference_size`, `export_size`, `export_fit`, `export_source_rect`,
  `export_scale`, `export_anchor`, `export_offset`,
  `export_bounds_padding`, and `export_infinite_policy`. This separates the
  style-authoring reference canvas from the physical SVG/MP4 canvas.
- **Rendered-bounds export source** — `export_source_rect='rendered_bounds'`
  measures visible finite geometry and labels before fitting content into the
  export canvas, with `clip`/`ignore` handling for infinite lines and rays.
- **CLI export-layout flags** — the `animageo` command now exposes
  `--reference-size`, `--export-size`, `--fit`, `--source-rect`,
  `--export-scale`, `--anchor`, `--offset`, `--bounds-padding`, and
  `--infinite-policy`.
- **Canvas reference metadata** — style JSON may now include
  `canvas.reference` for preview/export reference dimensions.

### Changed

- Visual `*_px` style values now resolve through `ptUnit_style` in split
  export-layout mode, so strokes, points, labels, tick marks, and angle arcs
  scale with the reference canvas when exporting to a larger physical size.
- `overlay.angle_radius` and `overlay.label_placement` are read directly from
  `StyleConfig`; they are no longer projected through `rendering`.
- Style import maps now require fully-qualified preset references such as
  `presets.color.main`, `presets.point_size.main`, and
  `presets.line_width.main`.

### Fixed

- **Keyframe playback initial state** — `AnimaGeoScene.play_keyframes()` now
  applies the first keyframe's values and `show`/`hide` visibility before
  playback starts, rebuilds geometry, and rerenders touched mobjects. MP4
  exports no longer show the saved `.ggb` editor state before the first
  keyframed motion begins.
- **Measure/AngleSize keyframe updates** — parsed keyframe values now update
  the real `.value` field for measure-like variables and mark dependents
  dirty, so downstream geometry rebuilds from the animated value.

### Removed

- Legacy style JSON migration is no longer part of runtime loading. Old
  top-level sections and legacy visual keys such as `line_width`, `font_size`,
  `ang_rdefault`, and `label_r_offset` now raise validation errors; canonical
  `*_px` fields are required.

### Tests

- Added coverage for export layout math, rendered-bounds export integration,
  CLI export options, canonical style validation, overlay automation access,
  construction-level parsed keyframe application, and scene-level
  first-keyframe state application.

## [1.2.0] - 2026-05-06

AI style-generation support release. This release adds a compact construction
summary exporter, machine-checkable style schema, and LLM prompt context for
generating style JSON plus optional loadCode-compatible DSL.

### Added

- **Compact construction summary exporter** — new
  `animageo.exporters.construction_summary` module with
  `construction_to_ai_summary(...)` and `write_ai_summary(...)`.
- **Scene-level AI summary API** —
  `AnimaGeoScene.exportStylePromptSummary(filepath=None, **kwargs)` exports
  `animageo-construction-summary/v1` as a dict or JSON file. The summary keeps
  names, canonical types, visibility, compact geometry, selected GGB style,
  construction dependencies, vars, groups, and parser diagnostics without raw
  `.ggb` XML.
- **AI style-generation context** —
  `docs/ai_style_generation_context.md` defines the style-layer model,
  resolver priority, when to use `overlay.per_type`, `overlay.per_name`,
  automation blocks, and when optional Python DSL is appropriate.
- **AI output contract** — the context now explicitly separates generated
  `STYLE_JSON`, optional `PYTHON_DSL`, and `NOTES`. `PYTHON_DSL` is limited to
  the body of a file passed to `scene.loadCode(...)`; it must not contain
  `AnimaGeoScene`, `loadGGB`, render/export calls, Manim animation code, or
  scene orchestration.
- **NOTES contract for LLM output** — the AI context now requires notes for
  ambiguity, construction-summary-based selections, overlapping geometry such
  as polygon sides vs. separate segments, DSL usage/avoidance, relative
  numeric changes, visibility changes, automation blocks, out-of-scope
  requests, and other follow-up-relevant assumptions.
- **Style JSON Schema** — `docs/ai_style_json_schema.json` provides a
  Draft 2020-12 schema for validating generated style JSON.
- **Construction summary documentation** —
  `docs/construction_summary.md` documents the
  `animageo-construction-summary/v1` format and exporter options.
- **AI style-generation fixture** — `examples/ai_style_generation_scene10/`
  contains a reproducible GeoGebra-based test setup for AI-generated style JSON
  and optional DSL, with output SVG generated into the same folder.

### Changed

- **Documentation navigation** — README, docs index, and API docs now link to
  the construction summary exporter, AI context, and style JSON schema.
- **AI guidance for layer choice** — the context now prefers `overlay.per_name`
  when a supplied construction summary is sufficient to resolve computed
  requests such as "longest segment", and reserves DSL for missing geometry or
  logic that cannot be represented by style JSON alone.
- **AI guidance for polygon-side highlights** — the context now warns that
  imported polygon outlines can duplicate side segments; highlighted sides
  should be raised above normal stroke layers or the polygon outline should be
  restyled/disabled, with the choice reported in `NOTES`.

### Fixed

- **GeoGebra `Point(Conic)` import** — points constrained to conics now keep
  their canonical curve parameter from GGB XML coordinates. This fixes scenes
  where a point on a hyperbola was imported as `data=None`, causing downstream
  `Line`, `Intersect`, `Segment`, `Distance`, `CircumcircleArc`, and `Angle`
  commands to remain unbuilt.
- **Wrapped arc containment** — `Arc.contains()` now compares point angles in
  the same unwrapped interval as the arc itself. This fixes
  `CircumcircleArc(A, M, B)` choosing the opposite side of chord `AB` when the
  intended arc crosses the `0` angle.
- **GeoGebra arc/ray intersections with Unicode labels** —
  `Intersect(Arc, Ray, index)` and `Intersect(Arc, Segment, index)` are now
  dispatchable, and command inputs such as `β` are treated as simple
  identifiers instead of being rewritten through empty phantom expressions.
- **DSL redefinition redraws dependents** — `loadCode()` and `putCode()` now
  run a final full rebuild before rerendering, so redefining an imported GGB
  element (for example `E = Rotate(...)`) updates downstream elements such as
  `Segment(B, E)` instead of drawing stale geometry.

### Tests

- Added coverage for construction summary export.

## [1.1.1] - 2026-05-01

Patch release for the resolver-based style architecture introduced in 1.1.0.
This release separates GGB import data, project overlay rules, explicit
Python/DSL edits, and construction visibility into distinct layers.

### Fixed

- **Explicit Python/DSL style priority** — `elem.style` is now reserved for
  explicit Python/DSL writes and remains the highest-priority style layer.
  `overlay.per_type` / `overlay.per_name` are no longer materialized into
  `elem.style`; the resolver reads overlay rules lazily from `StyleConfig`.
  This fixes cases like `d.style.stroke_width_px = 10` being overwritten by
  overlay during `addAllGeometry()` / `updateAllGeometry()`.
- **GGB visual import isolation** — GGB visual values are stored in
  `elem.ggb_style` and consumed by the resolver below overlay and above
  defaults. `import.enabled=false` now disables the whole visual import layer
  without clearing `elem.ggb_raw` or seeding defaults into `elem.style`.
- **Construction visibility separation** — GeoGebra `show_object` and
  `ImportPolicy.visible` are treated as geometry/construction visibility
  (`elem.visible`), not visual style. Runtime `Show` / `Hide` /
  `addAllGeometry(show=False)` stay above imported visibility.
- **Label placement resolver call** — label-placement code now consistently
  uses the imported `_resolve_style(...)` helper, preventing the
  `_resolve is not defined` crash when automatic label placement is enabled.
- **Canonical import color remapping** — `import.colors` writes canonical
  `#rrggbb` colors plus optional opacity into `elem.ggb_style`, avoiding raw
  RGB/RGBA arrays and stale-opacity edge cases.
- **Background export parity** — `rendering.background` is applied consistently
  to Manim preview/MP4 and SVG/PNG export.
- **Renderer no longer needs web-side legacy style bridge** — render paths read
  canonical `StyleConfig` defaults and resolver values directly; web clients do
  not need to add legacy `defaults.tick` / `defaults.arrow` / angle aliases.
- **GGB unsupported-command warning cascades** — GGB loading now records root
  unsupported commands in `scene.geo.command_diagnostics`, deduplicates repeats,
  and suppresses downstream `NoneType` warning cascades in non-strict mode.
- **Unicode GGB identifiers in generated expressions** — names such as `α_2`
  now resolve before command dispatch, fixing expression chains like
  `4 * (α_2 - 90°)` that previously degraded into `Sub(str, AngleSize)`.

### Changed

- **Resolver priority is explicit**:
  `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults`.
- **Overlay API compatibility** — `scene.applyOverlay()` / `StyleOverlay.apply`
  remain as no-op compatibility hooks; rendering uses lazy resolver reads.
- **GGB import/adaptation coverage** — `import.point_size` now maps GGB point
  sizes to `size_px`, and `ImportPolicy` covers raw-derived fields such as
  `stroke_opacity`, `stroke_dash_ratio`, `label_text`, `angle_range`, and
  `tick_count`.
- **Legacy visual fields are input migration only** — `line_width`,
  `ang_width`, `strich_*`, `arrow_*`, `label_r_offset`, and `font_size` in
  style JSON are normalized to canonical pixel-unit keys before resolving.
  Runtime render code reads `stroke_width_px`, `tick_*_px`, `arrow_*_px`,
  `label_radial_offset_px`, and `font_size_px`.
- **Manim baseline updated** — runtime dependency now requires
  `manim>=0.20.1,<0.22`, matching the latest PyPI release tested before
  1.1.1.
- **Documentation refresh** — README, API docs, architecture docs, style guide,
  field-name reference, import-policy docs, examples, and snapshots now
  describe the separate `ggb_raw` / `ggb_style` / `overlay` / `elem.style`
  layers.

### Tests

- Full suite: `1036 passed` with Manim Community `0.20.1`.

## [1.1.0] - 2026-04-29

Style-system release: semantic presets, per-type defaults, overlay parity for
GGB and DSL scenes, and a rewritten style guide. This release completes the
transition to the canonical style schema and removes the temporary alias and
normalization layer.

### Added

- **Semantic `presets` registry** — canonical style constants now live under
  `presets`: `presets.color`, `presets.point_size`, `presets.line_width`,
  `presets.angle_radius`, `presets.tick`, `presets.arrow`, and
  `presets.font_size`. Names such as `main`, `bold`, and `aux` are conventions;
  user-defined names are valid and can be referenced from other blocks.
- **Generic style references** — values like `presets.color.main`,
  `presets.line_width.bold`, and `presets.arrow.main` are resolved
  recursively by `StyleConfig`.
- **Structural preset includes** — per-type style maps can use `$include` to
  merge reusable structured presets, for example vector arrows and segment
  tick marks.
- **Scene background styling** — `rendering.background` accepts a hex color or
  a preset reference such as `presets.color.background` and is applied to the
  Manim camera background.
- **Canonical tick/arrow style keys** — renderers now understand
  `tick_length_px`, `tick_width_px`, `tick_shift_px`, `arrow_length_px`, and
  `arrow_width_px` through the resolver.

### Changed

- **`presets.color` is the only color registry** — builtin styles, examples,
  docs, and runtime access now use `presets.color`.
- **`defaults` is now a per-type baseline** — defaults choose or include
  semantic presets for element types (`point`, `segment`, `vector`, `angle`,
  etc.) instead of storing scene-level `angle` / `tick` / `arrow` / `font`
  knobs directly.
- **Overlay application order** — `overlay.per_type` and `overlay.per_name`
  apply uniformly to GGB-imported and DSL-created elements, with `per_name`
  winning over `per_type`.
- **Style import maps** — `import.colors`, `import.point_size`, and
  `import.line_width` accept fully qualified preset refs as well as bare
  preset names. `import.colors` now normalizes remap results to hex colors and
  applies target opacity separately, preserving the current opacity when the
  target does not specify one.
- **GGB import adaptation** — `import.point_size` is now applied by
  `applyStyle`; `ImportPolicy` can target raw-derived visibility, labels,
  angle range, tick count, line opacity and dash style. `obj_color` raw data
  exposes normalized `hex` and `opacity` aliases for policy callables/remaps.
- **ImportPolicy scope** — `ImportPolicy` is now limited to raw-GGB
  adaptation. Type/name stylization moved fully to `overlay.per_type` and
  `overlay.per_name`, which apply uniformly to GGB and DSL elements.
- **Documentation and examples** — README, style docs, field-name reference,
  migration guide, policy examples, and the HTML style guide were updated to
  the canonical `presets` schema.

### Removed

- Removed top-level `palette` and `palette.*` reference resolution.
  Use `presets.color` and `presets.color.<name>` references.
- Removed normalization of old scene-level `defaults` blocks for tick, arrow,
  font, and angle-radius settings. Use `presets.tick`, `presets.arrow`,
  `presets.font_size`, `presets.angle_radius`, and per-type `defaults`.
- Removed `strich_*_px` per-element aliases. Use `tick_length_px`,
  `tick_width_px`, and `tick_shift_px`.
- Removed public support for automation settings under `rendering`; use
  `overlay.angle_radius` and `overlay.label_placement`.

### Tests

- Full suite: `1013 passed` with Manim Community `0.19.0`.

## [1.0.2] - 2026-04-24

Security, correctness, dead-code cleanup and manim 0.20 compatibility pass.
Driven by a full library audit; every item below has a regression test.

### Removed (breaking)

- **``animageo/_stubs.py``** — 613-line orphan IDE-stub snapshot that
  referenced pre-1.0 field names (``Measure.x``, ``Angle.angle``).
  Unreferenced from package; deleted.
- **``mult_ff`` / ``mult_fm`` / ``mult_mf`` / ``mult_if``** — unreachable from
  dispatch (``f`` was never registered in ``type_to_shortcut``); deleted.
- **Unused Lark parser block in ``ggb_parser.py``** (~130 lines: grammar +
  ``GeoGebraTransformer`` + ``parse_geogebra_xml``). Never called.
  ``lark`` removed from ``pyproject.toml`` dependencies.
- **DSL sandbox**: ``type`` and ``getattr`` removed from ``SAFE_BUILTINS``
  (classic sandbox escape via ``type(x).__mro__[-1].__subclasses__()``).
  Use ``isinstance(x, Cls)`` and the new ``type_name(x)`` DSL helper.
- **CLI ``-d/--debug`` flag** — semantic reversed to ``action='store_true'``
  (intuitive: ``-d`` turns debug ON). Previously was ``store_false`` which
  meant ``-d`` silenced debug output.

### Added

- **``AnimaGeoScene.resetScene()``** — explicit state wipe for reusing one
  scene instance across render jobs. Called automatically by ``loadGGB``.
- **``setElementStyle(..., update=True)`` / ``setVisible(..., update=True)``**
  — auto-rerender by default so changes are visible immediately.
  ``update=False`` defers for bulk operations.
- **``COMMAND_REGISTRY`` + ``list_commands()``** in ``lib_commands``. Dispatch
  uses the explicit registry instead of ``globals()``. Emits a warning when
  a command name doesn't match any implementation (previously silent ``None``).
- **Pixel-invariant decoration overrides** — per-element opt-in keys in
  ``elem.style``: ``strich_len_px`` / ``strich_rshift_px`` / ``arrow_width_px``
  / ``arrow_length_px``. When set, rendered at an absolute pixel size
  regardless of canvas ``ptUnit``. Scene-level defaults keep legacy
  scale-with-canvas semantics (backward-compatible).
- **DSL helper ``type_name(x)``** — returns ``type(x).__name__`` as a string.
  Safe stand-in for the removed ``type(x).__name__`` pattern.

### Fixed

- **Shell / Python injection in ``python -m animageo``** — CLI used
  ``os.system`` with f-string interpolation of user-supplied arguments into
  generated Python source. Rewritten to ``subprocess.run`` with argv-list
  and ``repr()``-escaped placeholders.
- **ZIP slip + zip bomb in ``.ggb`` loader** — ``ZipFile.extractall`` ran
  without path validation. New ``_safe_extract_ggb`` rejects traversal
  paths, absolute paths, archives with >4096 members, and >256 MB
  uncompressed total.
- **``loadGGB`` state leakage** — a second ``loadGGB`` on the same scene
  instance stacked new geometry on top of the old (visible as leftover
  elements from the prior file). Now starts from a fresh ``Construction``.
- **Global ``_bbox_cache`` thread-safety** in ``label_placement`` — added
  ``threading.Lock``; extended cache key with ``tex_template`` identity.
- **``Angle.equivalent`` / ``AngleSize.equivalent``** — used the non-existent
  ``.angle`` attribute; would raise ``AttributeError``. Now use ``.value``.
- **``are_congruent_aa`` / ``are_complementary_aa``** (``lib_commands``) —
  same ``.angle`` bug; 100% crash on any invocation. Fixed.
- **``_apply_interp_value`` for Measure vars** — wrote to ``.x``, which
  doesn't exist on ``Measure`` (phantom attribute created; real ``.value``
  unchanged). Keyframe animations on Measure variables were silently no-ops.
- **``Element.value()`` for Measure/AngleSize/Boolean** — circular import
  between ``lib_vars`` and ``lib_elements`` left those classes unbound at
  method-call time → ``NameError``. Fixed with local imports.
- **``font_size_px`` dead key** — builtin defaults and overlay shipped the
  key, but the renderer only read ``font_size`` (manim units), silently
  dropping pixel-invariant font overrides. Renderer and label placement
  now prefer ``font_size_px`` through the resolver.
- **``label_radial_offset_px``** — name said pixels, code treated value as
  manim units. ``5`` meant 5 MU ≈ 500 px. Now honoured as actual pixels.
- **Sandbox hardening** — see "Removed" above for ``type``/``getattr``.
- **Marching-squares ``_edge_point``** — unguarded divisions by corner-
  difference could yield ``inf``/``nan`` for near-coincident corner values.
  Now collapses to mid-edge.
- **``intersect_*`` near-zero endpoint detection** — ``if a == 0`` on a
  float could miss a true zero rounded to ±1e-17, losing a valid root.
  Replaced with ``abs(a) < 1e-12`` + symmetric case at the other endpoint.
- **``play_keyframes`` on a missing element** — silently skipped via
  ``info is None``; now logs a warning with context so debug traces aren't
  lost.

### Changed

- **Python requirement** relaxed from ``>=3.13`` to ``>=3.10``. Code uses
  PEP 604 unions and PEP 585 generics; no newer syntax.
- **Dependency pins** — ``numpy<3.0``, ``manim<0.20`` upper bounds added
  (manim has had breaking API changes between minor versions).
- **Internal project notes**: stale statistics removed (test count,
  render-method count).
- **``style/schema.py``** doc table split into pixel-invariant vs
  scale-with-canvas unit classes (previously mixed).

### Docs

- The HTML guide's downloadable example scene was using pre-1.0 API names
  (``show_label``, ``stroke_width``, ``technic``,
  ``ggb_export.import_policy``); synced with the current source (the guide
  tree has since moved to ``docs/guide/``).
- ``examples/main.py``: 15 SyntaxWarnings from invalid escape sequences
  (``'$...\circ...$'``) fixed with raw-string prefix.

### Tests

- 937 → 988 (+51 new regression tests).
- 0 regressions; ``_safe_extract_ggb`` path traversal / bomb prevention,
  DSL sandbox escape vectors, state-reset on ``loadGGB``, overlay reaching
  renderer for stroke/font/size, ``Element.value()`` for each variable
  type, ``Angle.equivalent`` symmetry, float-tolerance edge cases, CLI
  injection payload lock-in, pixel-invariant decoration overrides.

### Compatibility

- Tested against manim 0.19.0 and 0.20.1. Upper bound in ``pyproject.toml``
  relaxed to ``manim>=0.19.0,<0.22``.
- Fixed manim 0.20 deprecations in our code:
  ``VMobject.get_cap_style()`` → direct ``cap_style`` attribute read.
- Fixed NumPy 2.0 deprecations in our code: replaced 2-D ``np.cross``
  calls (``lib_commands.area`` and ``are_concurrent_lll``) with explicit
  scalar ``x1*y2 − y1*x2`` expressions.
- Silenced the startup ``pytest-asyncio`` deprecation via
  ``[tool.pytest.ini_options]``.

## [1.0.1] - 2026-04-24

Patch release: reliability fixes in rendering and DSL re-definition.

### Fixed

- **Arc / CircleSector rendering** (`animageo.py`) — both renderers read `elem.data.sizes`, but the geometry classes expose the attribute as `angles`. Any scene containing Arc or CircleSector crashed during `CreateMObject`, cascading through dependents. Renamed to `elem.data.angles`.
- **`.contains` typos in `lib_commands.py`** — `arc.centerontains(...)` / `line.offsetontains(...)` were pre-1.0 search-and-replace artifacts with no matching method on the target classes. Broke `intersect_Cl` (arc∩line), `circumcircle_arc_ppp` / `circumcircle_sector_ppp`, `contained_by_pc` / `contained_by_pl`. All five call sites now use `.contains(...)`.
- **DSL command failure with forward-ref Vars** — when a command's inputs contain a forward-reference Var with no data yet, `Construction.apply()` only wrote `None` into outputs that *already existed* as elements. Phantom outputs (e.g., intermediate `_3` from `4 + x` arithmetic) were silently skipped, so `element(name)` later returned `None` and `styleGeometry`-style code raised `AttributeError`. Fix: `apply()` now creates placeholder elements for all outputs, including not-yet-existing phantoms.
- **`Construction.rename()` broke downstream dependency graph** — when a DSL file redefined a GGB-loaded element (e.g., `X = A + x * (B - A)` where `X` was already a Point in the GGB), the `_forget(X) + rename(phantom, X)` sequence cleared every `state[downstream].inputs` reference to `X`, but did not restore them for the new command using `X`. Symptom: animating the Var re-computed `X` itself, but `q1`/`g`/… that depended on `X` never rebuilt, so the animation was visually frozen. Fix: `rename()` now re-runs `updateStateLevels` on every command that references the new name.

### Notes

- All 937 unit tests continue to pass.
- No API surface changes.

## [1.0.0] - 2026-04-23

First stable release. Substantial rewrite of the style system, parsers, and geometry core, with three new element types and full animation/labeling pipelines.

### Added

- **Python DSL (`animageo.dsl`, `parsers/dsl/`)** — exec-based mini-DSL replacing the old short-parser. Supports `for`/`if`/`def`, keyword args, tuple unpacking, live `.field` access on elements, proxy arithmetic (`A-B`, `-v`, `abs(x)`), `f(x) = expr` sugar for functions, and auto-generated `.pyi` stubs per scene.
- **Style subsystem (`animageo/style/`)** — three-layer resolver architecture: package-shipped `builtin.json` defaults (pixels), user JSON defaults, `overlay.per_type` / `overlay.per_name` stylization, with explicit `elem.style[...]` writes always winning. Mini-DSL for policy values: `const:`, `scale:`, `quantize:`, `remap:`.
- **`ImportPolicy`** — configurable GGB-to-style mapping. Pass to `loadGGB` or embed under `import.policy` in the style JSON. Supports scalar, callable, and DSL-string rules. `scene.reloadPolicy()` reapplies a new policy without reparsing XML. Type/name overrides belong to `overlay.per_type` / `overlay.per_name`.
- **`Conic` element** — first-class conic stored as a 3×3 symmetric matrix with lazy classification into 9 types (circle / ellipse / parabola / hyperbola / intersecting / parallel / double lines / point / empty). Canonical parametrizations via eigendecomposition. Constructors: `Conic(matrix)`, `from_ggb_matrix`, `from_coeffs`, `from_string`.
- **`Function` element** — explicit `y = f(x)` with sympy parsing: `^` → `**`, Unicode `≤/≥`, chained comparisons, `If[...]` → `Piecewise`. numpy `lambdify` on the hot path.
- **`ImplicitCurve` element** — `F(x, y) = 0` for any sympy expression, rendered by marching squares.
- **Adaptive curve sampling (`geo/curve_sampling.py`)** — viewport-aware sampler with Liang–Barsky clipping, analytic t-ranges for parabola / hyperbola branches, marching squares for implicit curves. Hard `max_samples` caps guarantee no hangs on pathological curves.
- **Intersections across all type pairs** — analytic for `Kl` / `KK` / `Kc` (pencil method); numeric with sympy + `scipy.brentq` / `fsolve` fallbacks for `F*` and `I*`. 150+ commands in `lib_commands.py`.
- **Conic geometric constructors** — `Ellipse`/`Hyperbola` from foci + semi-axis, `Parabola` from focus + directrix, `Conic` from 5 points.
- **Conic properties** — `Center`, `Focus`, `Vertex`, `Axes`, `Directrix`, `Eccentricity`, `Polar`, `Tangent`.
- **Automatic label placement (`label_placement.py`)** — priority-ordered greedy solver with 8 candidate directions, analytic bisector placement for angles, EMA smoothing + anchor hysteresis for dynamic tracking, per-keyframe snapshots with interpolation.
- **Keyframe animation (`keyframes.py`)** — JSON-driven animation: free points, tparam-constrained points, numbers, angles, booleans; linear / smooth / in / out / in\_out easing; per-keyframe `show` / `hide`.
- **Batch API** — `setElementStyle(names, **kwargs)`, `setVisible(names, visible)`, `animating(...)` context manager.
- **Pixel-invariant sizing** — all GGB sizes (point radius, line width, font, arc, label offset) stored in pixel units, divided by `ptUnit` at render time. Same pixel output across canvas sizes.
- **Angle arc auto-sizing** — opt-in `rendering.angle_radius` scales arc radius by `(π/2 / angle) ** exp`, clamped by arm-length fraction. Shared between renderer and label placement.
- **Z-index tiers** — named constants in `constants.py` (`Z_FILL`, `Z_LABEL`, …).
- **`CreateMObject` dispatch** — split into 13 per-type `_render_<typename>` methods plus a small context builder. `CreateMObject` itself is a 20-line dispatcher.
- **Structured logging** — all modules use `logging.getLogger(__name__)`; no stray `print` in library code.
- **`CHANGELOG.md`** (this file).

### Changed

- **Version:** 0.1.11 → 1.0.0.
- **Python requirement:** bumped to `>=3.13`.
- **Metadata:** added MIT license, `Development Status :: 5 - Production/Stable`, audience and topic classifiers. Homepage switched to `https://`.
- **Topological rebuild** — Construction now uses Kahn's algorithm with cycle detection and per-element error recovery, so one broken element no longer aborts the whole scene.
- **CLI entry point** — `animageo` console script remains, unchanged surface.

### Fixed

- **`intersect_cc`** — edge-case reliability (tangent / coincident circles).
- **Angle arc radius units** — no longer collapse to sub-pixel values when `elem.style` is empty (builtin default of 17 px now applies).
- **GGB label offsets** — now scale proportionally with canvas size via `ptUnit_ggb`.

### Removed

- **`animageo/style.py` / `animageo/style_schema.py`** — replaced by the `animageo/style/` subpackage.
- **`animageo/parsers/short_parser.py`** — replaced by the Python DSL.
- **`requests` dependency** — was unused.
- **Legacy `geodynamic/` package** — earlier rename; no longer shipped in the wheel after build hygiene fix.

### Packaging

- **`pyproject.toml`** is now the single source of truth; `setup.py` reduced to a one-line shim.
- **`package-data`** — `style/builtin.json` and `*.pyi` stub files now ship inside the wheel.
- **`find_packages`** — restricted to `animageo*`; `tests/` is no longer included in the distribution.

[Unreleased]: https://github.com/ivaleo/animageo/compare/v1.8.1a5...HEAD
[1.8.1a5]: https://github.com/ivaleo/animageo/compare/v1.8.1a4...v1.8.1a5
[1.8.1a4]: https://github.com/ivaleo/animageo/compare/v1.8.1a3...v1.8.1a4
[1.8.1a3]: https://github.com/ivaleo/animageo/compare/v1.8.1a2...v1.8.1a3
[1.8.1a2]: https://github.com/ivaleo/animageo/compare/v1.8.1a1...v1.8.1a2
[1.8.1a1]: https://github.com/ivaleo/animageo/compare/v1.8.0a2...v1.8.1a1
[1.8.0a2]: https://github.com/ivaleo/animageo/compare/v1.8.0a1...v1.8.0a2
[1.8.0a1]: https://github.com/ivaleo/animageo/compare/v1.7.13...v1.8.0a1
[1.7.13]: https://github.com/ivaleo/animageo/compare/v1.7.12...v1.7.13
[1.7.12]: https://github.com/ivaleo/animageo/compare/v1.7.11...v1.7.12
[1.7.11]: https://github.com/ivaleo/animageo/compare/v1.7.10...v1.7.11
[1.7.10]: https://github.com/ivaleo/animageo/compare/v1.7.9...v1.7.10
[1.7.9]: https://github.com/ivaleo/animageo/compare/v1.7.8...v1.7.9
[1.7.8]: https://github.com/ivaleo/animageo/compare/v1.7.7...v1.7.8
[1.7.7]: https://github.com/ivaleo/animageo/compare/v1.7.6...v1.7.7
[1.7.6]: https://github.com/ivaleo/animageo/compare/v1.7.5...v1.7.6
[1.7.5]: https://github.com/ivaleo/animageo/compare/v1.7.4...v1.7.5
[1.7.4]: https://github.com/ivaleo/animageo/compare/v1.7.3...v1.7.4
[1.7.3]: https://github.com/ivaleo/animageo/compare/v1.7.2...v1.7.3
[1.7.2]: https://github.com/ivaleo/animageo/compare/v1.7.1...v1.7.2
[1.7.1]: https://github.com/ivaleo/animageo/compare/v1.7.0...v1.7.1
[1.7.0]: https://github.com/ivaleo/animageo/compare/v1.6.5...v1.7.0
[1.6.5]: https://github.com/ivaleo/animageo/compare/v1.6.4...v1.6.5
[1.6.4]: https://github.com/ivaleo/animageo/compare/v1.6.3...v1.6.4
[1.6.3]: https://github.com/ivaleo/animageo/compare/v1.6.2...v1.6.3
[1.6.2]: https://github.com/ivaleo/animageo/compare/v1.6.1...v1.6.2
[1.6.1]: https://github.com/ivaleo/animageo/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/ivaleo/animageo/releases/tag/v1.6.0
[1.5.0]: https://pypi.org/project/animageo/1.5.0/
[1.4.6]: https://pypi.org/project/animageo/1.4.6/
[1.4.5]: https://pypi.org/project/animageo/1.4.5/
[1.4.4]: https://pypi.org/project/animageo/1.4.4/
[1.4.3]: https://pypi.org/project/animageo/1.4.3/
[1.4.2]: https://pypi.org/project/animageo/1.4.2/
[1.4.1]: https://pypi.org/project/animageo/1.4.1/
[1.4.0]: https://pypi.org/project/animageo/1.4.0/
[1.3.4]: https://pypi.org/project/animageo/1.3.4/
[1.3.3]: https://pypi.org/project/animageo/1.3.3/
[1.3.2]: https://pypi.org/project/animageo/1.3.2/
[1.3.1]: https://pypi.org/project/animageo/1.3.1/
[1.3.0]: https://pypi.org/project/animageo/1.3.0/
[1.2.6]: https://pypi.org/project/animageo/1.2.6/
[1.2.5]: https://pypi.org/project/animageo/1.2.5/
[1.2.4]: https://pypi.org/project/animageo/1.2.4/
[1.2.3]: https://pypi.org/project/animageo/1.2.3/
[1.2.2]: https://pypi.org/project/animageo/1.2.2/
[1.2.1]: https://pypi.org/project/animageo/1.2.1/
[1.2.0]: https://pypi.org/project/animageo/1.2.0/
[1.1.1]: https://pypi.org/project/animageo/1.1.1/
[1.1.0]: https://pypi.org/project/animageo/1.1.0/
[1.0.2]: https://pypi.org/project/animageo/1.0.2/
[1.0.1]: https://pypi.org/project/animageo/1.0.1/
[1.0.0]: https://pypi.org/project/animageo/1.0.0/
