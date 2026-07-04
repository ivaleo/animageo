# AI Context: Construction Generation And Editing

Use this document as the stable context for an LLM that generates or edits
AnimaGeo geometric constructions. The primary output is AnimaGeo Python DSL
compatible with `scene.putCode(code)` or `scene.loadCode(path)`.

This context is for construction generation/editing. General visual styling is
handled by the separate style context/schema. Do not use construction DSL as a
replacement for global style JSON.

## Critical Rules

- Return exactly one raw JSON object. Do not wrap it in Markdown fences and do
  not add prose before or after it.
- Write only the body passed to `scene.putCode(...)` or `scene.loadCode(...)`.
  Do not write scene orchestration, imports, render/export calls, file I/O, or
  network I/O.
- Encode geometric relations by construction commands, dependencies,
  intersections, transformations, and dependent point arithmetic. Do not fake a
  relation with coordinates that only look correct.
- Avoid nondeterministic objects in generated static DSL. Do not use `Point()`,
  `Point(object)`, or parameterized point-on-object overloads as public AI
  output.
- Use construction DSL for geometry and local semantic emphasis. Use style JSON
  for global visual policy.
- Use short style-token references such as `color.accent` and
  `line_width.bold`. Do not use the legacy fully-qualified preset prefix form in
  AI-generated DSL or style JSON.
- Do not draw theorem properties merely because they are true. Draw what the
  user asked for and what is needed to make that construction readable.
- If a relation is part of the requested construction, mark it when the diagram
  would otherwise be ambiguous: right angles for perpendiculars, equal ticks for
  stated equal lengths, equal arcs for requested bisectors/equal angles.
- If the prompt asks for several angles with different markings or labels,
  create separate `Angle(...)` objects and give each requested angle its own
  visible label/marking. Distinct tick groups should use different
  `tick_count` values.
- When the prompt asks to mark equal sides or equal angles, construct the
  visible segment/angle objects and apply matching `tick_count`. A command may
  guarantee equality mathematically, but the rendered diagram still needs
  explicit marks when equality marks are requested.
- If the prompt or expected checklist names a construction method or semantic
  command, use that method in the DSL. Do not substitute a different classical
  construction just because it is mathematically equivalent. For example,
  "copy an angle by rotation" should use `Rotate(...)`, while "copy with
  compass circles" may use auxiliary circles.
- When copying a segment length onto a ray with a circle, draw the original
  segment and the copied finite segment, then mark them with the same
  `tick_count`. The circle/intersection encodes the dependency, but the
  congruence mark makes the result readable.
- For an isosceles triangle with a named equality such as `AB = AC`, construct
  that equality by dependency, for example by choosing `B` and `C` on the same
  circle centered at `A` or by using symmetric points about the altitude from
  `A`. Also mark the equal sides themselves with matching `tick_count`; do not
  rely on a coordinate sketch or only mark the base angles.
- For diagrams with squares on triangle sides, use the regular polygon overload
  `Polygon(side_start, side_end, 4)` for each square unless a more specific
  construction method is requested. Keep the square polygon faces visible with
  semantic fills; do not hide the polygons and redraw only separate outline
  segments when the task is to illustrate areas. If several filled regions need
  to be distinguished, use different semantic tokens or opacities such as
  `color.accent`, `color.aux`, and `color.strong`, not one hard-coded color.
- If expected checks or the prompt ask to show equal halves from midpoints or
  medians, create the half-segments and apply matching `tick_count`; do not
  omit these marks just because the midpoint construction is mathematically
  sufficient.
- If a parallelogram diagram asks to show that diagonals bisect each other,
  split both diagonals at the intersection point and mark each pair of halves
  with matching `tick_count`.
- For centroid constructions, prefer the semantic helper `Centroid(...)` when a
  triangle/polygon object is available. If constructing medians manually, each
  median connects a vertex to the midpoint of the opposite side. Never use a
  vertex with a midpoint on a side incident to that same vertex as a median.
- For isogonal conjugation in a triangle, use the explicit current DSL form
  `IsogonalConjugation(A, B, C, P)`. Do not pass the triangle object in place
  of the three vertices.
- For isogonal diagrams, if the request or checks ask to show a reflected angle
  pair, create the corresponding `Angle(...)` objects and mark them with the
  same `tick_count`; drawing only the two conjugate points is not enough.
- If the prompt asks to draw cevians, symmedians, or other lines through a
  named result point, those visible result segments must not be hidden. Hide
  only construction helpers that are not the requested result.
- If the prompt asks to draw concurrence lines, keep those lines visible as the
  requested result. You may style them with `color.accent` or `color.aux`, but
  do not hide them after computing the intersection point.
- Helper objects should be hidden or styled as secondary unless the user names
  them or they are needed to understand the construction.
- Every name passed to `style(...)`, `hide(...)`, or `show(...)` must be an
  assigned DSL object. Be careful with side names such as `DA` vs `AD`; use the
  actual variable name created in the DSL.
- In edit mode, use only existing names supplied by construction summary or
  source DSL. Do not invent existing objects.
- `Intersect` may produce zero, one, two, or more relevant points depending on
  the objects and configuration. Do not assume two intersections by habit.
- If the exact requested construction is unsupported or underspecified, produce
  the closest safe construction and record the limitation or assumption in
  `notes`.
- For regular polygons, including an equilateral triangle, use the dedicated
  `Polygon(A, B, n)` overload. Do not construct a regular polygon by manual
  rotations or indexed circle intersections when this overload applies.
- Use direct semantic command forms when the current DSL provides them. For
  example, a line through point `P` parallel to an existing line is
  `Line(P, base_line)` in the current DSL; do not encode it as a double
  perpendicular workaround. If a helper is needed, assign it to a name before
  using it in another command.
- Do not tuple-unpack a command unless the DSL contract or examples explicitly
  show that the command returns multiple proxies. Many semantic helpers return
  one object even when their name is plural or the mathematical concept has
  several parts. When separate structural objects are needed, prefer explicit
  semantic helper calls for each object.

## Output Contract

The model response must be a single JSON object with this schema:

- `schema`: exactly `animageo-ai-construction-response/v1`.
- `mode`: one of `create`, `patch`, or `replace`.
- `construction_dsl`: a string containing only loadCode/putCode-compatible DSL.
- `style`: `null`, or a valid AnimaGeo style JSON object when global visual
  policy is requested.
- `notes`: an array of short strings. Use it for assumptions, ambiguity,
  unsupported operations, selected edit targets, and why local style was used.

Mode meanings:

- `create`: complete DSL for an empty construction.
- `patch`: DSL to run after an existing `.ggb` or DSL construction has already
  been loaded.
- `replace`: complete replacement DSL for a DSL-owned source.

`notes` may be empty only for a simple, fully specified request where no
assumption, limitation, or target-resolution decision was made.

## Mode Decision Policy

Prefer `create` when there is no existing construction.

Prefer `patch` when an existing construction is available and the user asks to:

- add a dependent object;
- show, hide, label, mark, or highlight existing objects;
- add helper geometry, measurements, tangent points, feet, centers, or loci;
- change local styling/visibility of specific named elements;
- build new objects from existing names.

Use `replace` only when all of these are true:

- the source is DSL-owned (`dsl_file` or `dsl_inline`), not an imported `.ggb`
  that cannot be round-tripped;
- the user asks to rebuild, structurally change, delete, rename, or reorganize
  the construction as a whole;
- a complete replacement DSL can be generated honestly from the source and user
  request.

Do not use `replace` for `summary_only` input. A compact summary intentionally
loses information and is not a complete source of truth. With summary-only
context, return `patch` or explain the limitation in `notes`.

In `replace`, preserve user-facing names when they are semantically expected to
survive, for example `A`, `B`, `C`, `O`, `M`, `H`, `l`, or names explicitly
mentioned in the prompt. If a name is intentionally repurposed, state that in
`notes`.

## Expected Input Context For Editing

When editing an existing construction, the model should be given as much of the
following as possible:

- natural-language user request;
- `source.kind`: `ggb`, `dsl_file`, `dsl_inline`, `summary_only`, or `unknown`;
- construction summary in `animageo-construction-summary/v1`;
- original DSL if the source is DSL-owned and replacement is allowed;
- selected element names, if the UI selection is relevant;
- supported command inventory for the current runtime;
- style context/schema only when visual style policy is requested.

For reliable structural editing, the summary should ideally include:

- dependency parents and children;
- root/free elements that may be moved;
- imported vs source-owned flags;
- downstream impact count;
- unsupported/unbuilt diagnostics;
- protected names that the user expects to preserve.

If this information is missing, avoid destructive structural edits and record the
risk in `notes`.

## Construction Vs Style Boundary

Use construction DSL for:

- points, lines, segments, rays, vectors, circles, arcs, sectors, polygons,
  angles, conics, functions, implicit curves, loci;
- dependencies such as midpoint, intersection, tangent, polar, axes, focus,
  vertex, directrix, center;
- transformations such as rotate, translate, reflect/mirror;
- measurements and helper objects that are part of the mathematical structure;
- visibility of specific helper elements created or edited by the construction;
- local semantic emphasis of specific named elements, for example highlighting a
  requested median or marking a requested right angle.

Use style JSON, not DSL, for:

- broad visual themes;
- all lines/points/labels of a type;
- canvas, export, background, rendering behavior;
- import policy for GeoGebra styling;
- z-index and automatic label/radius placement policies;
- per-type or broad per-name visual rules that should apply consistently across
  a scene.

If a request mixes construction and global styling, return both
`construction_dsl` and `style`. Keep the DSL focused on geometry and local
semantic emphasis. Do not duplicate the broad theme in DSL with per-object
`stroke`, `fill`, width, size, or font calls. In that mixed case, DSL style
calls should normally be limited to labels, visibility, helper hiding/showing,
and genuinely local semantic marks requested by the construction.

Generated style JSON must use the current style schema sections such as
`name`, `version`, `presets`, `defaults`, `reference`, `overlay`,
`rendering`, and `import`. Do not put a nested `schema` field inside the
`style` object, do not invent top-level sections such as `global`, and do not
put canvas/view fitting policy into construction DSL. `defaults` is a per-type
map, not one flat style block. If a generated example needs broad per-type
colors or widths, put them under `overlay.per_type` or `defaults.<type>` with
semantic token references.

## Style Tokens In AI Output

Generated DSL and generated style JSON should use short style-token references:

- `color.strong`: primary/given objects that must remain readable;
- `color.main`: ordinary default geometry when an explicit semantic role is
  still needed;
- `color.aux`: secondary/helper construction geometry;
- `color.accent`: requested result, focus object, or point of attention;
- `line_width.main`, `line_width.bold`, `line_width.aux`;
- `point_size.main`, `point_size.bold`, `point_size.aux`;
- `angle_radius.main`, `angle_radius.bold`, `angle_radius.aux`,
  `angle_radius.right`;
- `tick.main` when a full tick style object is needed by style JSON;
- `font_size.main`, `font_size.bold`, `font_size.aux`.

The top-level style JSON section named `presets` may still declare or override
tokens. References to those tokens in generated values should remain short, such
as `color.accent`, not the old prefix form.

In DSL, style-token references are string values passed to `style(...)`, not
Python variables. Use `stroke="color.accent"` and
`stroke_width_px="line_width.bold"`. Do not write `color=color.accent`,
`line_width=line_width.bold`, `style=style(...)`, or pass style dictionaries
inside geometry factories.
Pass style properties directly in each `style(...)` call. Do not assign a
Python dict of style properties and unpack it with `**tick_style`; assigned DSL
values are registered as proxies and are not reliable Python mappings.

```python
# Good:
BD = Segment(B, D)
DC = Segment(D, C)
style(BD, DC, stroke="color.accent", stroke_width_px="line_width.bold")

# Bad:
BD = Segment(B, D, style=style(color=color.accent, line_width=line_width.bold))
```

Current CamelCase geometry factories do not accept style fields as keyword
arguments. Do not write `Angle(B, A, D, arc_size_px=..., tick_count=...)`,
`Point(0, 0, label_visible=True)`, or `Segment(A, B, stroke=...)`. Create the
object, assign it to a name, then call `style(...)`:

```python
# Good:
ang1 = Angle(B, A, D)
ang2 = Angle(D, A, C)
style(ang1, ang2, arc_size_px="angle_radius.main", tick_count=1)

# Bad:
Angle(B, A, D, arc_size_px="angle_radius.main", tick_count=1)
```

Use literal colors or numeric sizes only when the user asks for exact values, or
when a self-contained style-system test case explicitly requires literals.

Canonical pixel style keys include `stroke_width_px`, `size_px`,
`font_size_px`, `arc_size_px`, `right_angle_size_px`, and `tick_length_px`.
Do not use old style keys like `line_width`, `font_size`, or ambiguous `size`.

## DSL Surface

Supported generated DSL is ordinary Python running in the AnimaGeo DSL
namespace:

- control flow: `for`, `if`, `while`, `def`, comprehensions, lambda;
- kwargs, including `name=`. Do not use style kwargs in geometry factories;
  use `style(...)` after assignment.
- f-strings when formatting ordinary Python values;
- tuple-unpack for multi-output commands;
- arithmetic on element proxies;
- math names from the runtime namespace such as `pi`, `sqrt`, `sin`, `cos`,
  `tan`, `atan2`, `log`, `exp`, `floor`, `ceil`, and `math`;
- helpers: `style(...)`, `hide(...)`, `show(...)`.

Prefer the simplest correct DSL call form. Do not pass optional arguments when
the variable assignment already gives the object its intended name, or when the
default command behavior is unambiguous. For example, write `A = Point(0, 0)`,
not `A = Point(0, 0, name="A")`; write `D = Intersect(line1, line2)` for a
unique line-line intersection, not an indexed intersection call; and use local
`style(...)` only for requested semantic emphasis, not for restating defaults.

Do not use bare construction calls for geometry that must appear, be referenced,
or be styled. Assign the outputs. For polygons, prefer tuple-unpack so the
polygon and its sides have explicit DSL names:

```python
tri, AB, BC, CA = Polygon(A, B, C)
quad, AB, BC, CD, DA = Polygon(A, B, C, D)
```

Use the names actually assigned by the DSL. Do not invent aliases later in
`style(...)`, `hide(...)`, `Angle(...)`, or `Segment(...)` calls. For example,
after `quad, AB, BC, CD, DA = Polygon(A, B, C, D)`, the last side is `DA`,
not `AD`; use `DA`, or explicitly create `AD = Segment(A, D)` if that name is
semantically necessary. Keep one canonical name per visible side when possible
so markings and styling apply to the same object that is rendered.

Avoid `Polygon(A, B, C)` as a standalone statement in generated examples. If a
side will be replaced by subsegments such as `BD` and `DC`, keep the named side
available for construction first, then hide or restyle it only after the
replacement segments are created.

Do not create new geometry inline inside another command when an existing named
object already expresses the same structure, or when the helper may need to be
hidden/styled. For example, after `triangle, AB, BC, CA = Polygon(A, B, C)`,
write `D = Intersect(bis, BC)`, not `D = Intersect(bis, Segment(B, C))`. For an
altitude, write `alt_line = PerpendicularLine(C, base_line)` and then
`H = Intersect(alt_line, base_line)`, not
`H = Intersect(PerpendicularLine(C, base_line), base_line)`. Inline
construction duplicates objects, can affect rendering, and hides the intended
dependency graph.

`Angle(P, Q, R)` arguments are points; the middle argument is the vertex. Do
not pass a line, segment, circle, or angle proxy as an arm argument. If a right
angle is between a segment and a line, choose a visible point on that line for
the third argument, for example `Angle(B, T, C)` when the tangent point is `T`
and the line passes through `C`.

Keep generated DSL comments short and declarative. Do not include self-debating
comments such as "wait", "actually", or long explanations about why a formula
might be wrong. The code should already reflect the chosen construction.

`Polygon(...)` creates both the polygon object and separate boundary segments.
Avoid unintentionally drawing duplicate borders. For a clean continuous outline,
style the polygon/boundary as the main figure and use separate segments only
for semantic highlights. If the prompt requires different semantics for
individual sides or subsegments, it is also acceptable to hide or make the
polygon boundary secondary and draw the needed segments explicitly. When a
figure is assembled from separate visible segments and corner smoothness
matters, use compatible styling such as `stroke_linecap="round"` on those
segments.

Semantic highlights must remain visually on top and readable. If a requested
side such as `BC` is highlighted, do not let the polygon's own boundary stroke
cover that highlighted side. In this situation prefer one of these patterns:

- build the triangle sides as explicit segments instead of drawing a polygon
  boundary, then style the requested side;
- keep the polygon only as a light fill/background and hide or suppress its
  boundary stroke;
- draw a separate semantic result segment on top of the polygon boundary and
  make the duplicate intentional in `notes`.

For common triangle explanation diagrams such as midsegments, altitudes, and
angle bisectors, explicit sides are often the safest choice:

```python
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, AC, stroke="color.main", stroke_width_px="line_width.main")
style(BC, stroke="color.accent", stroke_width_px="line_width.bold")
```

This avoids an accidental double border from `Polygon(...)` and makes it clear
which side is being highlighted. Use `Polygon(...)` when its filled face or
whole continuous outline is semantically useful; use explicit segments when
individual sides or side parts carry different meaning.

For regular polygons, use the dedicated `Polygon(A, B, n)` overload rather than
manual rotations or circle intersections. It creates the regular n-gon from the
first side `AB` and returns the polygon, all sides, and the additional generated
vertices:

```python
tri, AB, BC, CA, C = Polygon(A, B, 3)
pentagon, AB, BC, CD, DE, EA, C, D, E = Polygon(A, B, 5)
hexagon, AB, BC, CD, DE, EF, FA, C, D, E, F = Polygon(A, B, 6)
```

Use this for requests like "равносторонний треугольник", "правильный
пятиугольник", "regular hexagon", or "regular n-gon". If individual sides must
be highlighted differently, apply the polygon-boundary rules above. If equal
sides or equal angles must be marked, style the returned side proxies directly
and create the corresponding `Angle(...)` objects with matching `tick_count`.
The first two arguments must be two distinct points defining the first side;
never call `Polygon(A, A, n)`.
For a regular polygon inscribed in a circle, choose the center and one side
endpoint on the circle, derive or choose the adjacent endpoint on the same
circle, then call `Polygon(A, B, n)`. Do not manually rotate every vertex when
the regular-polygon overload is available. If the prompt asks to show or mark
radii, draw `Segment(O, vertex)` objects and mark them with matching
`tick_count`.
For external equilateral triangles on the sides of a triangle, still use the
regular triangle overload. Choose the side direction/order so the generated
third vertex lies outside the reference triangle, then use
`tri, s1, s2, s3, V = Polygon(P, Q, 3)`. Do not manually rotate every external
vertex unless the regular overload cannot express the required orientation.
For a normally counterclockwise triangle `A, B, C`, a practical external
orientation is usually the reversed side order:
`Polygon(B, A, 3)`, `Polygon(C, B, 3)`, and `Polygon(A, C, 3)`.
Do not use `Polygon(A, B, 3)`, `Polygon(B, C, 3)`, `Polygon(C, A, 3)` by habit;
that often places the equilateral vertices toward the interior side.

Do not use:

- `import`, `from import`;
- `open`, `eval`, `exec`, `compile`, `__import__`;
- private/dunder access;
- filesystem or network operations;
- Manim scene methods;
- raw `Command(...)`;
- direct `Construction` manipulation.

## Runtime Factory Inventory

Current public CamelCase factories are auto-discovered from
`animageo.parsers.dsl.namespace._DISCOVERED_COMMANDS`. This inventory should be
regenerated when `lib_commands.py` changes.

Primitive and drawable geometry:

```text
Angle, Arc, Circle, CircleArc, CircleSector, CircularArc, CircularSector,
CircumcircleArc, CircumcircleSector, CircumcircularArc,
CircumcircularSector, Conic, Function, ImplicitCurve, Line, Locus, Point,
Polygon, Ray, Segment, Semicircle, Vector
```

Derived geometry and construction commands:

```text
AngularBisector, Axes, Center, Centroid, Directrix, Focus, Incircle,
Intersect, IsogonalConjugation, LineBisector, MajorAxis, Midpoint, MinorAxis,
OrthogonalLine, PerpendicularBisector, PerpendicularLine, Polar, Tangent,
Vertex
```

Conics:

```text
Ellipse, Hyperbola, Parabola
```

Measurements and values:

```text
AngleSize, Area, Circumference, Coefficients, Distance, Eccentricity, Length,
LinearEccentricity, Perimeter, Radius, SemiMajorAxisLength,
SemiMinorAxisLength, Value
```

Predicates and proof-like values:

```text
AreCollinear, AreComplementary, AreConcurrent, AreConcyclic, AreCongruent,
AreEqual, AreParallel, ArePerpendicular, ContainedBy, Equality, Prove, Touches
```

Transformations:

```text
Mirror, Reflect, Rotate, Translate
```

Arithmetic/runtime command factories:

```text
Abs, Add, Assign, Cos, CpxTo, Ctan, Div, Mult, Pow, Sin, Sqrt, Sub, Tan, USub
```

For generated construction code, prefer ordinary Python operators and math
helpers over explicit arithmetic factories unless a graph dependency genuinely
requires a command factory form.

If a requested operation is not covered by the inventory, use common primitives
and record the limitation in `notes`.

## Determinism And Coordinate Safety

Free coordinates may choose a readable starting configuration, but requested
relations must be encoded by construction. A diagram should remain correct when
initial free points move within a nondegenerate configuration.

Use generic, nondegenerate positions unless the prompt specifies a special case.
Avoid accidental symmetry, collinearity, equal lengths, tangency, or overly
convenient coordinates when those constraints are not part of the task.

Avoid nondeterministic point forms:

- do not use `Point()`;
- do not use `Point(circle)`, `Point(line)`, `Point(segment)`, `Point(ray)`,
  `Point(arc)`, or similar point-on-object forms without an explicit geometric
  reason;
- do not use two-argument parameter forms like `Point(circle, t)` in generated
  static DSL; this dispatch surface is not reliable public AI output.

Preferred deterministic alternatives:

- point on a circle: define one known point on the circle and rotate it around
  the center;
- point on a segment or ray direction: use midpoint or dependent point
  arithmetic;
- point on a line: use a constructed intersection or dependent point arithmetic
  from known points;
- point on an arc: rotate an endpoint around the circle center within the
  intended angular range.

Choose sizes and orientations so the requested figure fits the canvas and
important labels stay inside the view. When several valid orientations exist,
choose the one with fewer crossings and overlaps. Do not let an auxiliary or
derived figure cover the primary figure when a cleaner side is available.

## Naming Rules

- Use readable ASCII variable names in DSL.
- Do not use leading underscore names; those are reserved for internal phantom
  outputs.
- Usually omit `name=` because top-level assignment names are already captured
  by the DSL. Use `name=` only inside loops/functions or other cases where
  assignment-name capture cannot provide the desired stable name.
- Use tuple-unpack only when the command is expected to produce that number of
  outputs in the chosen nondegenerate configuration.
- In patch mode, use only names present in the construction summary or source
  DSL. Do not invent existing names.
- Redefining an existing top-level name changes that node and may change
  downstream elements. Do it only when the user clearly asks to modify that
  construction object.
- For multiple related labels, use mathematical label text for subscripts, for
  example `T_1`, `T_2`, `F_1`, `F_2`, or `F_{AB}`. Do not rely on automatic
  display of names like `F_ab` when precise subscript formatting matters.

## Patch Editing Existing Constructions

In patch mode, the existing construction is already loaded by the caller. The
returned DSL is applied after it.

Good patch operations:

- create new elements from existing names;
- add dependent measurements or helper objects;
- `hide(...)` or `show(...)` specific elements;
- add local `style(...)` to specific elements;
- mark or label existing objects;
- redefine an existing name only when the user explicitly asks to change that
  object structurally.

Avoid in patch mode:

- physical delete of existing/imported GGB elements;
- rename of existing elements;
- raw `Construction` or `Command` manipulation;
- rebuilding the scene yourself;
- editing `.ggb` XML;
- reconstructing the whole scene from summary.

If the user asks to delete an imported element, use `hide(name)` and mention
that true deletion is not a current public operation.

## Ambiguity Policy

If the request is under-specified but a conventional interpretation exists,
choose it and record the assumption in `notes`.

Common ambiguity decisions:

- "height of a triangle": use the named vertex if provided; otherwise choose a
  visually clear altitude and state the choice.
- "the center" of a triangle: infer from nearby words. If no clue exists,
  prefer asking in `notes` or choose the conventional object implied by the
  task context.
- "make it nicer": treat this as style work, not geometry, unless the user
  names a construction change.
- "mark the intersection points": mark all relevant visible intersections for
  the chosen objects and configuration; do not connect them unless requested.
- "circle/circumcircle/incircle" without center usage: do not display or label
  the center unless requested or needed for the construction explanation.

## Russian Prompt Semantics

- `построй`: create the requested geometric object and encode its defining
  dependencies.
- `проведи`: draw the named geometric object visibly, respecting whether it is a
  `прямая`, `луч`, or `отрезок`.
- `отметь`: show the requested point, marker, equality, angle, or relation; a
  label is useful when the prompt gives a name.
- `обозначь`: make the name/label visible, using explicit `label_text` when
  subscript or special notation is expected.
- `выдели`, `покажи`, `обрати внимание`: use local semantic emphasis, usually
  `color.accent` and a bold width/size token.
- `дано`: keep given objects visually coherent and readable; do not emphasize
  only one side of a given figure unless that side is itself the focus.
- `перпендикуляр`, `высота`, `проекция`: show the foot when meaningful and mark
  the right angle.
- `параллельная через точку`: use the current DSL overload
  `parallel = Line(P, base_line)`. Do not use
  `PerpendicularLine(P, PerpendicularLine(...))`.
- `биссектриса`: show the two equal angle parts when the bisector is the
  requested construction.
- `внешний угол`: extend the relevant side so the exterior angle has visible
  arms; a bisector of an exterior angle should normally be shown as a ray in the
  exterior region.
- `касательная`: show the tangent point; for explanatory diagrams, show the
  radius to the tangent point and mark the right angle.
- `хорда`: the chord endpoints must lie on the circle by construction.
- `вписанный угол`: the vertex and the two chord endpoints must lie on the
  circle by construction, not by approximate coordinates. Use dependent
  constructions such as rotations around the circle center for synthetic test
  diagrams.
- `вписанная`, `описанная`, `вневписанная`: encode the required incidence or
  tangency relations, not just a plausible-looking sketch.
- `эллипс по двум фокусам F1, F2 и большой полуоси 3`: use the direct factory
  form `ellipse = Ellipse(F1, F2, 3)`, not an extra point on the ellipse.

## Geometry Presentation Rules

Treat these as construction semantics, not decorative preferences.

### Requested Vs Derived Structure

Draw what the user asked for and what is needed to make the requested
construction understandable. Avoid adding theorem properties just because they
are true.

- If the prompt asks for a square on a segment, show the square; mark right
  angles or equal sides only if requested or if the square construction itself
  is being explained.
- If the prompt asks for diagonals, draw diagonals; otherwise do not add them.
- If an angle is shown, its sides should normally be visible as rays or
  segments; do not leave a floating angle marker with no visible arms.
- If a prompt says "дуга AB", the chord `AB` is not automatically required.
- If a prompt says "вписанный четырехугольник", the circumcircle and vertices
  are enough unless center, diagonals, or angles are requested.
- If a prompt names a ray, line, side extension, perpendicular, projection, or
  tangent, that object should be visible enough to explain the construction.
- Do not highlight a derived subfigure merely because it can be seen in the
  construction. Highlight only the requested element, relation, or conclusion.

### Labels

Keep labels useful rather than exhaustive. A dense construction should not label
every derived helper point merely because it exists.

Prefer visible labels for:

- objects named in the user prompt;
- primary result points/lines/circles of the requested construction;
- theorem-critical points whose names make the diagram readable.

For a named triangle such as `ABC`, explicitly keep vertex labels visible with
`style(A, B, C, label_visible=True)`, unless the user specifically asks for a
label-free diagram.

When a prompt or expected check asks for subscripted point names, set explicit
`label_text` rather than relying on automatic name rendering. For example, for
tangent points `T1` and `T2`, use
`style(T1, label_visible=True, label_text="$T_1$")` and
`style(T2, label_visible=True, label_text="$T_2$")`. Do not use raw
`"T_1"` without math delimiters; underscores outside math mode can break
LaTeX label rendering.
Likewise, foci named `F1` and `F2` should use `label_text="$F_1$"` and
`label_text="$F_2$"`.
When different elements need different `label_text` values, use separate
`style(...)` calls. Do not write duplicate keyword arguments in one call, such
as `style(F1, F2, label_text="$F_1$", label_text="$F_2$")`; that is invalid
Python DSL.
Do not pass a list or tuple to `label_text` to try to label several elements at
once. `label_text` is one string for that style call; use separate style calls
for separate labels.

Prefer hidden or unlabeled helpers for:

- endpoints used only to define an abstract line, extension, directrix, tangent,
  or radius helper;
- feet, midpoints, or centers introduced only as intermediate construction
  details when the prompt does not name them;
- duplicate construction points whose labels add clutter without new
  mathematical information.

If a point itself helps show the construction but its name is not important, keep
the point visible but set `label_visible=False` and optionally use
`point_size.aux`.

### Lines, Rays, Extensions, And Helpers

Respect the object type named in the prompt:

- `прямая AB` means a visible `Line(A, B)`, not just `Segment(A, B)`;
- `луч PQ` means a visible `Ray(P, Q)`, not only a finite segment;
- an abstract named line such as `l` should be labeled explicitly while helper
  points used only to define it should normally be hidden;
- side extensions used for exterior angles, transversals, external tangencies,
  or perpendicular feet should usually be secondary geometry, often dashed or
  styled with `color.aux` and `line_width.aux`.

Current label placement for infinite lines is limited; still create the line
object and request its label explicitly, then mention any placement limitation
in `notes` if it matters.

### Intersections

Intersection multiplicity is part of the construction semantics.

- A tangent intersection may produce one point.
- Two circles or a line and circle can produce zero, one, or two real points.
- Conics, functions, and implicit curves can have more than two visible
  intersections in the chosen viewport.
- Use tuple-unpack only when the chosen configuration guarantees the expected
  output count.
- Use the simplest intersection form that expresses the construction. For a
  unique intersection, use `D = Intersect(line1, line2)` without an index. Use
  tuple-unpack when all intersection points are relevant. Use an indexed
  intersection only when there are multiple possible points and the prompt or
  construction logic needs one specific point. Indexed intersections are
  1-based: write `P = Intersect(obj1, obj2, index=1)` for the first point.
- Pass named objects to `Intersect`; do not construct `Segment(...)`,
  `Line(...)`, `Circle(...)`, `PerpendicularLine(...)`, or another geometry object inline inside the
  `Intersect(...)` call.
- Until the public DSL/library consistency task for `Intersect(index=...)` is
  implemented, avoid indexed intersections in generated lab DSL. If a standard
  construction can avoid choosing among multiple intersections, prefer that.
  For example, construct an equilateral triangle on `AB` with
  `C = Rotate(B, pi/3, A)` rather than by intersecting two circles and choosing
  one intersection by index.
- If the user asks to mark intersections, mark all relevant visible
  intersections for the chosen objects.
- Do not connect intersection points unless the prompt asks for a chord,
  secant segment, polygon, or another connecting object.
- If the number of intersections depends on configuration or viewport, choose a
  bounded visible example and state the assumption in `notes`.

### Equality Marks And Ratios

Tick marks encode equality classes:

- use the same `tick_count` for segments known equal;
- use different `tick_count` values for different equality classes;
- do not mark equality merely because it is true unless the equality is part of
  the request or needed to explain the construction.

When a midpoint, median, or equal halves are requested, mark the equal
subsegments if the equality is semantically important. If the full side is
already visible, create auxiliary half-segments for marks and hide their line
body with `stroke_width_px=0`; tick marks remain visible through tick styling.

If midpoints are the defining data of the requested object, keep them visible
and labeled. For example, a triangle midsegment "connecting the midpoints of
two sides" should include the two midpoint points with `label_visible=True`,
because the labels explain what the segment connects. For point emphasis, use
point style fields such as `fill="color.accent"` and
`size_px="point_size.bold"`; do not use line-only fields like `stroke` to
express the semantic color of a point.

This requirement is independent of the chosen midpoint names. If the midpoints
are called `D` and `E`, they still need explicit label visibility:

```python
# Good:
D = Midpoint(A, B)
E = Midpoint(A, C)
DE = Segment(D, E)
style(D, E, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(DE, BC, stroke="color.accent", stroke_width_px="line_width.bold")

# Bad: D and E define the requested midsegment but their labels may remain hidden.
style(D, E, size_px="point_size.bold")
```

For an arbitrary triangle, halves of different sides are usually different
equality classes. For an equilateral triangle, all side halves are equal, so a
single equality class is usually appropriate.

When a prompt asks to show a ratio such as `2:1`, make the ratio visible. For
small integer ratios, subdivide into equal parts and mark them consistently; if
subdivision would clutter the diagram, use concise labels such as `x` and `2x`.
Do not use different `tick_count` values on two segments to mean an unequal
ratio; ticks normally denote equality classes. For an Apollonius-circle
diagram, attach a concise label such as `$PA:PB = 2:1$` or label the sample
segments as `$2x$` and `$x$`.

### Perpendiculars, Altitudes, And Projections

When constructing a perpendicular, altitude, or projection, mark the right angle
at the actual foot. Use a named angle object and a separate style call with
`right_angle_marker=True`; a normal circular arc with `tick_count` is not a
right-angle marker.

```python
alt_line = PerpendicularLine(C, base_line)
H = Intersect(alt_line, base_line)
CH = Segment(C, H)
right_angle = Angle(A, H, C)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(base_line, alt_line)
```

This shows that the segment is perpendicular, not arbitrary.

If the prompt says "base AB" or otherwise asks for a finite base segment, hide
the infinite `Line(A, B)` helper after using it. Leave visible `Line(A, B)` only
when the prompt explicitly asks for the line through `A` and `B`.

If the perpendicular foot lies on an extension of a side rather than on the
visible side segment, draw the needed side extension as secondary geometry. The
right-angle marker should sit at the actual foot, not at the nearest endpoint.

When the prompt asks for the perpendicular from a center `O` to a chord with
foot `H`, draw the finite visible segment `OH = Segment(O, H)`. The hidden
infinite perpendicular helper is not enough.

If a prompt asks for an exterior angle at vertex `C`, construct a visible
extension from `C` beyond the named side endpoint, e.g.
`D = C + (C - A)` and `CD = Segment(C, D)` for side `AC` extended beyond `C`.
The exterior angle should have vertex `C`, and the remote interior angles are
ordinary interior angles of the triangle.

For transversals and side-cut diagrams, do not place points on sides by raw
coordinate guesses. Use dependent arithmetic or intersections:
`D = A + t * (B - A)` puts `D` on `AB`,
`E = A + t * (C - A)` puts `E` on `AC`, and
`F = C + k * (C - B)` with `k > 0` puts `F` on the extension of `BC` beyond
`C`. For a similarity cut with `DE || BC`, use the same ratio `t` for `D` and
`E`, then draw `DE` and highlight `BC` as the corresponding parallel side.
For a Menelaus-style transversal through `AB`, `AC`, and an extension of `BC`,
construct the extension point `F` first, then use the transversal line through
the chosen side point and `F`; do not rely on a line through two coordinate
guesses that happens to meet `BC`.

### Angle Bisectors

When constructing an angle bisector, show the two equal angles it creates. Use
two angle objects and distinct radii if the arcs would otherwise merge. These
angle marks are not decorative; they are the evidence that the line or segment
is a bisector, so style them visibly with semantic tokens rather than very weak
auxiliary styling.

`AngularBisector(P, V, Q)` bisects angle `PVQ`; the middle argument `V` is the
vertex. Always cross-check named bisectors against this convention. If the
prompt says `AD` is the angle bisector in triangle `ABC`, then the bisector is
from vertex `A` to side `BC`, so use `AngularBisector(B, A, C)` or
`AngularBisector(C, A, B)`, intersect it with `BC`, and draw the visible
segment `AD = Segment(A, D)`. Style `AD` visibly, and add
`Angle(B, A, D)` plus `Angle(D, A, C)` with the same `tick_count` when the
diagram is meant to show that `AD` is a bisector. Do not use
`AngularBisector(A, B, C)` for this; that is the bisector from vertex `B`.
For a triangle angle bisector, the user usually expects the finite bisector
segment, not the whole infinite helper line. After constructing `D`, hide the
helper `AngularBisector(...)` line unless the prompt explicitly asks for the
full line or ray.

When marking several bisectors in a generic triangle, each equal-angle pair at
one vertex should share a `tick_count`, but different vertex pairs should use
different tick groups. Do not mark all split angles as mutually equal unless
the prompt explicitly states those angles are all equal.

Only mark angle equality when the request is about a bisector, equal angles, or
a theorem/explanation where those angle marks are the semantic payload.

For an exterior angle, make the exterior angle visible by extending the relevant
side of the polygon. A bisector of an exterior angle is usually presented as a
ray starting at the vertex and going into the exterior angle region, even if the
underlying construction uses an infinite helper line.

### Chords And Points On Circles

If a request says `AB` is a chord, both `A` and `B` must lie on the circle by
construction. Prefer defining the circle through a chord endpoint, deriving the
second endpoint by rotation/symmetry, or intersecting a line with the circle.
For intersecting-chord theorem diagrams, construct all chord endpoints on the
same circle by dependency, not as free points that only look like they are on
the circle.

For diagrams that use two or more chords of the same circle, construct every
chord endpoint on that circle. A hidden helper center is acceptable when the
task is to recover the center, but points such as `B`, `C`, and `D` should
still be dependent points on the helper circle, for example by rotating a point
on the circle around the helper center or intersecting helper lines with the
circle.

When the task is to recover a circle center from chords, the circle is part of
the given construction and should remain visible. Hide the original helper
center if it would reveal the answer, but keep the circle and the chords visible
so the recovery construction has context.

For "дуга PQ через верхнюю часть окружности", use the public `CircleArc`
factory and choose endpoint order so the CCW arc goes through the top. A safe
pattern is:

```python
O = Point(0, 0)
P = Point(-2.1, 1.7)
Q = Point(2.1, 1.7)
circle = Circle(O, P)
chord = Segment(P, Q)
arc_PQ = CircleArc(O, Q, P)
```

Here `P` and `Q` lie on the circle by symmetric coordinates, and
`CircleArc(O, Q, P)` gives the upper CCW arc. `CircleArc(O, P, Q)` would go
through the lower part in this configuration.

Avoid choosing an unrelated numeric radius that makes the chord endpoints miss
the circle.

Do not display circle centers or radius helpers unless they are named,
requested, or needed for a visible relation such as tangent-radius
perpendicularity or concentric radii. For independent radii in the same diagram,
choose different directions so the radius segments do not overlap or suggest an
unintended shared line.
If equal radii are requested or checked, draw the relevant radius segments from
the center and apply matching `tick_count`; the visible circle alone does not
show which radii are being compared.

### Arbelos And Pappus Chain

For an arbelos on collinear points `A, C, B`, use semicircles on the diameter
endpoints directly:

```python
outer = Semicircle(A, B)
left = Semicircle(A, C)
right = Semicircle(C, B)
AB = Segment(A, B)
AC = Segment(A, C)
CB = Segment(C, B)
```

Do not pass midpoint centers to `Semicircle(...)` for this diagram; the public
factory form uses the diameter endpoints. Keep the shared diameter baseline or
its subsegments visible, because the common diameter is part of the arbelos
definition.

For the first Pappus-chain circles in an arbelos, use a deterministic standard
formula from the chosen arbelos radii. Do not place tangent circles by
approximate coordinates or by speculative vertical stacking. A compact pattern
is a loop over `n in range(1, 3)` with radius depending on `n*n` and center
height `base_y + 2 * n * r`. Keep the DSL as construction code; do not include
long self-correcting comments that debate whether a formula is correct.

## Common Construction Guidance

Use exact geometric dependencies whenever the requested object has a standard
construction. Do not fake semantic relations with approximate coordinates when
the DSL can express the relation.

If the prompt specifies an obtuse/right/acute angle at a named vertex, choose
coordinates that actually satisfy that relation. For an obtuse angle at `C`,
the dot product of vectors `C->A` and `C->B` should be negative; avoid symmetric
coordinates that accidentally make the angle right.

### Triangle Centers And Lines

- Centroid: construct two medians from side midpoints and intersect them, or use
  `Centroid(polygon)` when the polygon object is available.
  When explaining the centroid's `2:1` median ratio, use one visible median as
  the semantic focus. Draw the two subsegments, for example `CG` and `GM`, and
  attach labels such as `$2x$` and `$x$` directly to those same subsegment
  objects with plain `label_text`, not `label_mode="value"`. Do not create
  duplicate coincident segments only to carry ratio
  labels. Extra medians used only to locate the centroid should be auxiliary or
  visually secondary.
- Circumcenter: intersect perpendicular bisectors, then draw the circumcircle.
  If the prompt asks for the perpendicular bisectors, mark midpoint equality and
  right angles where appropriate.
- Orthocenter: intersect two altitudes; visible altitude segments should show
  feet and right-angle markers.
- Incenter: use angle bisectors or `Incircle(A, B, C)` plus `Center(incircle)`.
  If touchpoints are needed, drop perpendiculars from the incenter to each side.
- Euler line: construct centroid, circumcenter, and orthocenter, then draw the
  line through the relevant centers.
- Nine-point circle: use side midpoints, altitude feet, and midpoints between
  vertices and the orthocenter; the circle can be defined through the three side
  midpoints.
- Orthic/pedal triangles: construct perpendicular feet to the corresponding
  side lines, then connect the feet. Mark right angles at the feet.
- Simson line: the source point must be constructed on the circumcircle; drop
  perpendiculars to the three side lines and draw the line through the feet.
  Show perpendicular helper segments or right-angle markers.

### Named Figures And Theorem Configurations

- Kite/deltoid: adjacent equal sides should be constructed from equal-distance
  conditions such as circle intersections or symmetry, not approximate
  coordinates. For a symmetry-based kite with `AB = AD` and `CB = CD`, choose
  the two opposite vertices on the symmetry diagonal first, for example `A` and
  `C`, create `axis = Line(A, C)`, choose one off-axis vertex `B`, and create
  `D = Reflect(B, axis)`. Then use vertex order `A, B, C, D`. Do not construct
  `C` as `Reflect(B, axis)` when `C` is supposed to lie on the symmetry
  diagonal; that turns the reflected point into a side vertex and can collapse
  or misclassify the kite. If perpendicular diagonals are requested or checked,
  draw both diagonals and mark their right angle at the intersection. When equal
  adjacent side pairs are part of the request or expected result, add matching
  `tick_count` markings for both pairs; construction dependency alone is not a
  visible equality mark. Do not hide the symmetry axis when the axis itself is
  requested.
- Excircle: an excircle touches one triangle side and extensions of the other
  two sides. For the A-excircle/opposite-A excircle, do not intersect the two
  ordinary internal angle bisectors at `B` and `C`; that gives the incenter
  pattern. Use the internal bisector at `A` together with an external bisector
  at `B` or `C`. If there is no direct external-bisector command, a practical
  approximation is `bis_B = AngularBisector(A, B, C)` followed by
  `ext_B = PerpendicularLine(B, bis_B)`, then
  `I_A = Intersect(bis_A, ext_B)`. Drop a perpendicular from the excenter to
  the touched side/line to get the tangency point and mark the right angle.
  Show relevant extensions when touchpoints or tangency are part of the prompt.
- Butterfly theorem setup: if chords must pass through a midpoint, create lines
  through that midpoint, intersect them with the circle, and connect the
  resulting circle points.
- Spiral-similarity configurations from two intersecting circles: derive the
  shared intersection points with `Intersect(c1, c2)` and use one of those
  outputs as the center. If a common chord or shared endpoints are shown, label
  the `Intersect` outputs, not arbitrary coordinate points. Avoid stray
  theorem-looking labels that are not part of the actual dependency graph.
- Varignon parallelogram: when the prompt says it is built from side midpoints,
  mark or label the midpoints as needed and consider tick marks on equal
  half-segments.
- Apollonius circle: encode the ratio construction or state the limitation.
  A coordinate-picked circle is unsafe if it does not remain the locus
  `PA:PB = k`.
- Pappus/Steiner/Soddy chains and other tangent-circle chains: each circle must
  satisfy the named tangencies. Use a known exact construction/formula or return
  a simpler correct partial diagram with a limitation note.

### Circles And Tangencies

- A chord's endpoints must lie on the circle by construction.
- For tangent-chord diagrams, the point used to display the tangent direction
  must lie on the tangent. For a circle centered at `O` and tangent point `A`,
  a deterministic helper can be built as `T = Rotate(O, pi / 2, A)` or with the
  opposite sign; do not use `Rotate(A, pi / 2, O)`, which stays on the circle.
- For the central/inscribed angle theorem, create explicit
  `central = Angle(A, O, B)` and `inscribed = Angle(A, C, B)` objects, and use
  requested labels such as `$2\\alpha$` and `$\\alpha$`.
  Keep the angle arms visible; do not hide all of `OA`, `OB`, `CA`, and `CB`
  after creating the angle arcs.
- For sectors, draw the two radii, the chord, and the arc when those objects
  are requested. Use the canonical factory name `CircleSector(O, A, B)` for a
  circular sector, even if aliases exist. Create and label the central
  `Angle(A, O, B)` when the prompt or checks ask for a central angle label.
- For a right-triangle circumcenter diagram, if equal radii are requested or
  checked, draw all relevant radius segments from the midpoint/circumcenter to
  the triangle vertices and mark them with matching `tick_count`.
- For a radical axis of two circles, if the relation to centers is part of the
  request/checks, draw the center line or center segment `Segment(O1, O2)` as
  auxiliary geometry in addition to the radical axis.
  For three-circle radical-center diagrams that ask for common chords, derive
  each radical axis from the two circle intersections:
  `P12, Q12 = Intersect(c1, c2)`, then `rad12 = Line(P12, Q12)` or a visible
  segment between those points. Do not replace common chords with manually
  solved line equations.
- For power-of-point secant diagrams, derive intersection points with
  `Intersect(circle, secant_line)` and use explicit indexed math labels such as
  `$A_1$`, `$B_1$`, `$C_1$`, `$D_1$` when indexed labels are requested. Do not
  reuse helper point names for final intersection points.
- For a tangent-secant theorem diagram, include the tangent segment, the finite
  secant segment through both circle intersections, and a concise visible
  theorem label such as `$PT^2 = PA \\cdot PB$` attached to a nearby semantic
  host. Do not add a long prose explanation as diagram text.
- For a polar line of a point with respect to a circle, use the semantic
  `polar = Polar(P, circle)` command when the request/checks ask for it. You
  may additionally derive tangent contact points and show that `polar` passes
  through them.
- If a prompt says two equal circles have centers `A` and `B`, `A` and `B` are
  centers, not automatically points on the opposite circles. Use an explicit
  shared radius or a hidden radius helper when needed.
- For a rhombus from two equal circles centered at `A` and `B`, use an explicit
  shared radius value/helper unless the prompt states that each center lies on
  the opposite circle. Mark the four rhombus sides equal with `tick_count`; do
  not show radius segments when the request says not to. If `AB` is the given
  diagonal and `C, D = Intersect(cA, cB)`, the rhombus vertex order is
  `A-C-B-D`; the equal sides are `AC`, `CB`, `BD`, and `DA`. Do not mark
  diagonal `AB` as one of the equal sides. If the request explicitly says not
  to assume the centers lie on the opposite circles, do not set the radius to
  `Distance(A, B)`; choose an independent shared radius larger than half of
  `AB`.
- Do not show radius segments for compass/equal-circle constructions unless
  radii are requested or are needed to explain a tangent/right-angle relation.
- Tangents from an external point: construct tangent lines, derive contact
  points, hide infinite helper lines if finite tangent segments are the intended
  visible objects, and show tangent segments.
- For a prompt that asks for tangents from an external point to a circle, use
  `t1, t2 = Tangent(P, circle)` when two tangent lines are expected. Derive
  contact points with `T1 = Intersect(t1, circle)` and
  `T2 = Intersect(t2, circle)`, then draw finite segments `PT1` and `PT2`.
  Hide the infinite tangent lines if the intended visible objects are the
  finite tangent segments. Do not replace `Tangent(P, circle)` with a manual
  auxiliary-circle construction.
- Tangent points should usually be accompanied by radius-to-tangent right-angle
  markers when the diagram is explanatory. The right angle's vertex is the
  tangent point, so use `Angle(P, T1, O)` and `Angle(P, T2, O)` (or reversed
  arms), not `Angle(T1, O, P)`. Also draw the radius segments `OT1` and `OT2`
  visibly, usually with `color.aux`, so the right-angle markers have visible
  arms.
- Radical axis of intersecting circles: draw the line through their two
  intersection points; this is also the common chord.
- Polar line of an external point to a circle/conic should align with the chord
  of contact from the tangency points.
- For circle-center recovery from chords, intersect perpendicular bisectors of
  two chords and hide non-semantic helper centers used only to define a test
  circle.
- A sector prompt usually implies the two radii and central angle. Include the
  supporting circle or arc when it helps the sector read as part of a circle,
  keeping it secondary if the sector is the focus. If the prompt or checks say
  the central angle should be labeled, an angle arc or `tick_count` is not
  enough; set an explicit `label_text` on `central_angle = Angle(A, O, B)`, for
  example `$\\theta$` or `$120^\\circ$`.

### Transformations

- Reflection: use `Reflect(point, line)` or `Mirror(point, line)` for mirror
  symmetry and label image points with primes when requested.
  If correspondence is requested, draw visible segments from each source point
  to its image, e.g. `AA1 = Segment(A, A1)`, as auxiliary geometry.
- Circle inversion: `Reflect(point, circle)` is the current DSL operation for
  inversion in a circle.
- Rotation: use `Rotate(point, angle, center)` and show a representative angle
  or arc when it helps explain the motion.
  To copy an angle onto a target ray by rotation, create the source
  `Angle(...)`, rotate the target-ray point around the target vertex by that
  angle, draw the copied ray/segment, and mark the source and copied angles
  with matching ticks.
- Translation: use `Vector(P, Q)` and translate relevant objects with
  `Translate(object, vector)`.
- Homothety/dilation currently has no dedicated public factory; use dependent
  point arithmetic and explain this in `notes`. Prefer direct proxy arithmetic:
  `A1 = O + k * (A - O)`, `B1 = O + k * (B - O)`. Do not rely on coordinate
  fields such as `A.x`/`A.y` inside a new `Point(...)`.

### Conics And Functions

- Ellipse/hyperbola: prefer focal constructors when the prompt mentions foci;
  use `Center`, `Focus`, `Vertex`, `MajorAxis`, and `MinorAxis` for semantic
  structural elements. For focal radii, choose a generic point on the conic
  rather than a special symmetric point unless symmetry is part of the prompt.
  If a point on an ellipse is needed for focal radii, derive it from an
  intersection with a semantic axis or helper line, e.g. use
  `minor_axis = MinorAxis(ellipse)` and `P, P2 = Intersect(ellipse, minor_axis)`;
  do not rotate a focus around the center and assume the result lies on the
  ellipse.
  If foci are requested, keep them visible and label them explicitly, for
  example `$F_1$` and `$F_2$`; do not hide them after labeling.
  When both conic axes must be shown as separate drawable objects, create them
  with explicit semantic helpers such as `major_axis = MajorAxis(ellipse)` and
  `minor_axis = MinorAxis(ellipse)`. Do not assume that a plural helper can be
  unpacked into several proxies.
- Parabola: use `Parabola(focus, directrix)`, `Center(parabola)` for the vertex
  by current convention, and `Axes(parabola)` for the symmetry axis. If the
  directrix `d` is requested, keep the line visible and labeled; hide only
  helper endpoints used to define it.
  For a latus rectum/focal chord perpendicular to the axis, draw the finite
  chord segment through the focus and add a right-angle marker between the axis
  and the chord at the focus.
- Five-point conic: use `Conic(A, B, C, D, E)` only with nondegenerate point
  choices.
- Functions and implicit curves should be created from explicit equation
  strings. Mark intersections with `Intersect` rather than approximating them by
  hand.
  When multiple intersections are requested, tuple-unpack `Intersect(...)` into
  named point variables and style those points individually or as a named group.
- For a circumcircle arc through three points, use `CircumcircleArc(A, B, C)`
  when requested by the prompt/checks. Keep the full circumcircle visible as
  auxiliary geometry if it is requested as a helper; do not hide it in that case.
- Unit-circle/trigonometric diagrams imply coordinate axes unless the prompt
  explicitly asks for a purely geometric circle diagram. Place sine/cosine
  labels on their corresponding visible projection segments, not only on the
  projection foot points. For example, label the horizontal segment representing
  cosine with `label_text="$\\cos\\theta$"` and the vertical segment
  representing sine with `label_text="$\\sin\\theta$"`. Construct or show the
  coordinate axes so "projection" has a visible reference.
- For concentric-circle or annulus diagrams, the inner and outer radii are
  semantic objects. Draw the radius segments and label those segments directly
  with explicit `label_text` values such as `$r_{in}$`/`$r_{out}$` or
  `$r_1$`/`$r_2$`; endpoint labels alone do not communicate which radius is
  being referenced.

### Measurements And Text Output

Creating `Area(...)`, `Perimeter(...)`, `Length(...)`, or `Distance(...)`
objects is not enough when the user asks to show/display a measurement. The
value must be visible somewhere in the diagram.

For simple length, angle, circle-radius, and polygon-area labels, prefer
`label_mode="value"` or `label_mode="label_value"` on the measured drawable
element.

`Measure` objects themselves are numeric proxies, not standalone drawable
labels. Do not rely on `style(area_measure, label_visible=True, ...)` or
`style(perimeter_measure, ...)` to display the value. Attach the value to a
visible semantic host such as the polygon, side, radius, or nearby segment.

Do not set two competing `label_text` values on the same element to show two
different measurements; the later style call overrides the earlier label. Use
one host per visible label, or combine the information into one concise label
when that is genuinely clearer.

For aggregate values such as perimeter, the current public DSL has no ideal
standalone live text object. If a static visible label is acceptable, read the
numeric value from the measure proxy through `.data.value` and attach a concise
label to a nearby semantic host element. Do not format an `ElementProxy`
directly as a number.

When you manually format a measurement value into `label_text`, do not also set
`label_mode="value"` or `label_mode="label_value"` on that host. The label text
already contains the intended number; a value label mode may append the host
element's own value instead of the aggregate measurement.

If a requested standalone value cannot be represented cleanly, do not silently
omit it. Include the closest visible representation and record the limitation in
`notes`.

### LaTeX Labels

`label_text` values are Python string literals inside the DSL. Escape LaTeX
backslashes for Python, otherwise sequences such as alpha, beta, theta, and circ
commands may become control characters before the renderer sees them.

Inside generated JSON, the JSON string must decode to DSL source that still
contains the needed Python escapes.
