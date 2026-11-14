# Import: `.ggb` and the classic graph as documents (`native.from_ggb`, `native.from_construction`)

animageo 1.10.0a1–1.10.0a3, kernel stage L5, stages 1–3 (plan L5 §3). The package
`animageo.native.convert` translates the classic `Construction` — the graph
`ggb_parser` builds from a `.ggb` and the DSL builds from a scene — into an
`animageo-construction/v1` document, by one table of commands. What does not
translate is reported with a reason; nothing is translated falsely.

```python
from animageo import native
doc, report = native.from_ggb("file.ggb", id_namespace=ns)          # partial by default
doc, report = native.from_construction(constr, id_namespace=ns)     # strict by default
native.has("from_ggb"), native.has("from_construction"), native.has("import_report.v1")
```

`doc` is `None` when nothing translates; with `empty_document=True`
(1.10.0a2, `native.has("from_ggb.empty_document")`) it is then a valid
document without operations — a file of pictures only gives the web a
document to place them on. `id_namespace` (a `uuid.UUID` or
its string) is given by the caller — the web passes the uuid of the import
(decision 6). `mode="strict"` raises `native.ConvertError` (`.items` — the
objects that are not editable) unless everything is editable;
`mode="partial"` returns the document of what translates.

## 1. The table `convert/dsl_map.json`

A row per classic dispatch key (`strFullCommand`: `midpoint_pp`,
`intersect_lci`, `polygon`; the same key for a `.ggb` and a DSL scene):

- an op row `{factory, ggb, op, args, outputs, index?, input?}` — `args`
  names the op slot of each classic input (`null` — not an argument, e.g.
  the output number; `{"ends": [a, b]}` — a segment whose two points fill
  `a` and `b`) or `{"variadic": slot}`; `outputs` — slots by classic output
  number, `{"byValue": [slots]}` (§3) or `{"pattern": "polygon_sides" |
  "regular"}`; `index` — the input holding the output number;
  `input: "pathParameter"` — a point on a path whose parameter is projected
  from the value;
- a free row `{free: "point" | "angle", value}` — `Point(x, y)` and
  `AngleSize(0.7)` of the DSL with literal arguments;
- a formula row `{factory, ggb, op: "number.expression", formula, outputs:
  ["number"]}` (1.10.0a2, `mapVersion` 2) — `formula` is an AST v1 tree
  (`docs/native/expr.md`) where `{"input": i}` stands for classic input `i`:
  a number of the document becomes `{"ref": k}` of `refs`, a constant
  `{"num": v}`; `from_ggb` puts the formula of a nested arithmetic expression
  into the formula that uses it (`d = (c - 7)^2 / 4` is one
  `number.expression` with the reference `c`);
- an unmapped row `{unmapped: reason, note?}` — the reason of the report
  (`no_registry_op`, `formula_unsupported`, `unsupported_signature`); the
  note is English for the table, the report shows a Russian `detail`
  (`construction.NOTE_DETAILS`).

`opsWithoutClassic` lists the registry ops no classic key builds, with the
reason. `map_problems(seed=…)` checks both directions: every classic key has
a row, every op and slot exists, every registry op is used or listed, every
command of the web seed (`docs/native/seed/translate-2026-10.json`) is in a
row. `python -m animageo.native convert map [--check]`.

1.10.0a1: 477 classic keys; 140 op rows → 47 ops, 2 free rows; the rest
unmapped: conics, functions and coordinates — `no_registry_op` until stage
L4; arithmetic of values — `formula_unsupported`; predicates (`AreParallel`,
…) — `no_registry_op`; intersections with conics, points by numbers —
`unsupported_signature`.

The current importer also maps `Ellipse(F1, F2, P)`, `Hyperbola(F1, F2, P)`,
`Parabola(F, directrix)`, five-point `Conic`, conic centres, foci, vertices,
axes and line/ray/segment intersections with conics to the existing registry.
Conic equations such as `y = a*x^2` retain numeric references. Their homogeneous
matrices are compared with the saved GeoGebra matrices up to a nonzero factor.
Intersection slots are assigned together by saved value, then kept fixed during
movement. Branch selection and projection of points on paths follow graph order.
Since registry 1.8 (`mapVersion` 5) `Intersect` of two conics, of a conic
and a circle or of a conic and an arc (with or without the output number)
is `intersect.conic_conic`: its four slots are bound by the saved values as
those of `intersect.circle_circle`. Since registry 1.9 (`mapVersion` 6)
`Point(<conic>)` is `point.on_path` on the conic: its saved point is
projected (`native.project_input`), the input keeps `pathKind` (the kind of
the conic now) and on a hyperbola the `branch` of the saved point; the saved
coordinates check it. `ClosestPoint(<conic>, P)` and `ClosestPoint(<function>,
P)` are `point.closest` (the nearest branch of a hyperbola; a graph searched
over the window of the saved view), checked by the saved point; the classic
gained `closest_point_Kp` and `closest_point_Fp` for them. A function the
import reads itself is an argument of a command by its element (its XML type
`function` gives the signature letter `F`). `Point(<conic>, t)` stays
`unsupported_signature`, as `Point(<circle>, t)`: the registry has no
operation for a dependent path parameter (GeoGebra `PathParameter`).
General intersections with functions (`Intersect(f, …)`) and `Intersect(a, b,
<Point>)` and conic transformations still require registry support and keep
their fallback reasons. A bare `pi`
(`π`) argument, as in `Rotate(B, pi, O)`, is read as its number.

Since 1.14.0 the angle of `Rotate(obj, <expression>, center)` that the classic
makes into angle arithmetic it does not translate (`-theta`,
`4 * (α_{2} - 90°)`, `180° - γ`) is read from the text of the argument by the
number reader (`°` is `·(π/180)`, angles in radians) and becomes a hidden
`number.expression` helper of the rotation (`transform.rotate`, registry 1.4).
A number or an angle slider is a reference of the formula; an angle of a
figure (`Angle(B, C, D)`) is first measured by a hidden `measure.angle`
helper. The rotation is value-checked by its image against the saved
`<coords>`. An argument read but outside the formulas (`floor(α)`, a point,
`x(A)`, a command in it) is `formula_unsupported` with the expression in
`detail`; one the reader cannot read keeps the classic path. An angle
argument the classic translates itself (a numeric slider: `-a`, `a/2`)
keeps its translation; `Rotate(P, α, O)` with a bare angle of a figure stays
`unsupported_signature`. The parity fixture
`animageo/native/parity/v1/ggb/ggb_rotate_angle_formula.json` (scene in
`tests/native/import/scenes/`) holds both kinds of rotation and a function
saved with its label in front, with their helpers, for the other
implementations of the kernel.

Since registry 1.10 (`mapVersion` 7; 1.14.0 already used version 6), the
import reads `<expression type="point|vector">` from the XML into typed
`point.expression` / `vector.expression` formulas. Points and vectors are
pairs inside the formula; the XML element type determines the output.
Supported forms include `A + v`, `A + B`, `2A − B`, `(a, b)`,
`(cos(α), sin(α))`, `(x(A), y(v))`, and `(1, f(1))`. Numeric components,
function arguments and the root are checked by the typed kernel language
(`expr.md` §6); `x(A)` alone is numeric and cannot define a point.
References retain their first-occurrence order and identity, so changing
an input recomputes the formula. A formula vector starts at the origin.
An unsupported formula is `formula_unsupported`, with its source expression
in `detail`: lists, polar or 3D coordinates, commands inside coordinates,
vector division, mixed point/number addition and unsupported functions
cannot become free copies of their saved positions.

The new reader also handles `Vector[(a, 0)]` in command arguments, for
example `Rotate(Vector[(a, 0)], α, O)`. Its private `vector.expression`
helper has no name, `appearance.role: aux`, hidden and locked appearance,
and `origin: {kind: auto, source: <host operation ID>}`; deleting the host
removes its helpers. Existing lowerings (`Vector[(0, 2.5)]`, `Vector[(-v)]`,
`Vector[(a * v)]`, `Translate`) keep their operations and minimum registry.
A constant point formula without references, such as `(sqrt(2), 0)`,
remains `point.free` with the saved coordinates. This source reader is
specific to `from_ggb`; classic `from_construction` keeps its language.

### Function analysis (registry 1.11, mapVersion 8)

`from_ggb` reads these commands directly from XML, including commands with
no classic implementation. The seven analysis operations remain in
`opsWithoutClassic`; this does not add factories to `from_construction`.
Their report `signature` retains the original source arguments, including
on refusal, rather than inventing a classic dispatch key.

| GeoGebra source | Native operation |
|---|---|
| `Root(p)` | `function.roots_polynomial` |
| `Root(f, start)` | `function.root_near` |
| `Root(f, a, b)` | `function.root_interval` |
| `Roots(f, a, b)` | `function.roots_interval` |
| `Extremum(p)` | `function.extrema_polynomial` |
| `Extremum(f, a, b)` | `function.extrema_interval` |
| `Intersect(p, xAxis[, k])`, either input order | `function.roots_polynomial`, static `root.k` when indexed |
| `Intersect(f, yAxis[, 1])`, either input order | `point.expression`, `(0, f(0))` |
| Numeric `v = f(a)` | `function.value` |
| `P = (a, f(a))` | Existing typed `point.expression` |

Here `p` must have a native polynomial body; `f` must have a native function
AST. A conic or implicit curve cannot stand in for a function. Inline bodies
such as `Root(x^2-a)` use hidden `function.expr` helpers. Numeric arguments
such as `pi`, `2*pi`, `a+1` use the safe numeric reader and, when necessary,
hidden `number.expression` helpers. Named numbers retain their identity as
references even when their saved values are equal. Helpers have no display
name, are hidden and locked with `role: aux`, and belong to the host
operation through `origin: {kind: auto, source: <host operation ID>}`.
Deleting the host removes its helpers under the ordinary deletion rules.
These seven operations require registry 1.11; ordinate intersections and
typed coordinate points alone still require only registry 1.10. Consumers
must implement the operations, not merely accept the registry number.

An unindexed multi-output command stays one operation. Finite saved points
are matched one-to-one to native solutions using the import tolerance;
ambiguous or conflicting bindings are refused. Saved undefined outputs keep
their source ordinal as their native rank. An explicit x-axis index always
selects `root.k`, irrespective of saved coordinates. Empty output names and
names without a source `<element>` reserve their ordinal but create no
element. Capacity is the maximum of one, the highest required native slot
and the highest source ordinal plus one, up to 100. A larger source capacity
refuses the file with `import_too_many_objects`. Only source elements are
bound; evaluation never adds or deletes points. Missing ranks produce
`branch_absent` for a nonempty result set, otherwise `no_root` or
`no_extremum`. Defined repeated outputs report the full `detail.found`
before capacity is applied. Ranks can change when roots merge or disappear;
they do not track a physical branch through a bifurcation.

Saved `<coords x y z>` are normalized to `(x/z, y/z)` for nonzero `z`,
and numeric `<value val>` checks scalar values. Both sides undefined pass;
a defined value on only one side fails. Missing saved evidence yields
`differs/value_unchecked`; a mismatch yields `differs/value_mismatch`.
The imported operation and its dependencies remain live in both cases.
Neither disagreement nor an unsupported signature becomes a free point.

Compatibility follows the native deterministic profile, with these limits:

- Near-root Newton and bracket fallback can choose a different root from
  GeoGebra, including after changing the start. A saved match checks one
  frame and does not establish equal attraction basins.
- Interval root searches retain tangencies that GeoGebra may omit. A native
  defined slot against a saved undefined point is a mismatch; slots are
  never skipped to manufacture a match.
- The zero function gives `coincident` in every native root mode, including
  single-root modes where GeoGebra may save `(0, 0)`.
- Interval searches work on detected finite continuous pieces around holes,
  poles and jumps. Their results do not promise equal numerical completeness
  on every source expression.
- Native elements remain fixed when GeoGebra would grow or remove outputs.
  Additional roots require explicit document editing. Saved-coordinate tests
  cover particular inputs; they do not certify all static x-axis indices,
  starts, intervals or zero plateaus of `If`.

CAS lists, nonpolynomial global modes, unbounded nonpolynomial x-axis
intersections, dynamic or invalid indices, point-valued search inputs and
unknown extra arguments are explicit `unsupported_signature` refusals.
Unsupported formula language is `formula_unsupported`; malformed numeric
text is `parse_error`. A source function's explicit domain also applies to
ordinate and scalar evaluation, without clamping the requested abscissa.

Reproduce the function source archives, scenes and shared parity data with
`python -m tests.native.ggb_function_analysis_fixtures [--check]`.
`tests/native/import/functions/` includes reproducible synthetic archives
and saved GeoGebra 5.4.936.0 scenes. Their `ggb_function_*` fixtures in
`parity/v1/ggb/` include import report expectations and changed inputs;
analytical assertions check roots and extrema independently of generation.

### Tangents, normals and slopes (registry 1.12, mapVersion 9)

`has("tangency")` announces five operations: graph tangent at an abscissa,
strict tangent at a conic point, distinct conic tangents through a point,
conic tangents parallel to an oriented line, and scalar line slope.

| Source | Native lowering |
|---|---|
| `Tangent(x,f)` | `line.tangent_function_at(function=f,x=x)` |
| `Tangent(A,f)` | the same op with an owned live x(A) helper; y(A) is ignored |
| `Tangent(P,K)`, noncircular K | `line.tangents_from_point_conic` |
| `Tangent(l,K)`, including a circle | `line.tangents_parallel_conic` with `conic_section` |
| `Slope(l)` | `line.slope` |
| `OrthogonalLine(Q,t)` | existing `line.perpendicular`; Q remains its dependency |

The importer captures original XML commands before classic parsing, preserving
signatures even when classic fails on undefined or infinite values. Native
curve definitions and numeric inputs supply the calculation. Saved line
coefficients are normalized as `[a,b,c]` for ax+by+c=0 and compared using
`tol.import`; slopes and intercepts are not matching keys. Missing coordinates
give `differs/value_unchecked`; unmatched coordinates give
`differs/value_mismatch`. Neither case becomes a free line.

Conic outputs are matched as a group. Finite evidence takes priority;
undefined saved outputs reserve distinct undefined slots, preferring their
source ordinal. Without saved evidence, an unused ordinal is retained.
Two named coincident saved lines refuse the entire new conic producer with
`unsupported_signature` and a multiplicity explanation; dependents form the
normal unsupported closure. Many-to-one aliases are not introduced. Labels,
IDs, visibility and original aN ordinals are retained. An empty `aN=""`
creates no element and never shifts a later output.

Slot bindings stay fixed after import. The native ordering follows the
canonical polar direction for tangents through a point and the oriented base
normal for parallel tangents; see the operation pages. At a merged contact,
native has one distinct tangent (`found=1`) and an absent second branch;
GeoGebra can retain two coincident named lines. Native elements do not appear
or disappear during evaluation, and `found` counts the full solution set
before output capacity. A saved match is evidence for that frame, not a
promise of equal branch history under every edit.

Graph tangents expose `line` and `touch`. Build a normal through the contact
with `line.perpendicular(point=touch,base=line)`; for a strict conic tangent
use the original point. Imported source Q→tangent→normal dependencies remain
live. Inline curves and coordinate helpers are hidden, locked, `role: aux`,
with `origin: {kind: auto,source: <owner operation ID>}`. The scalar x(A)
dependency is composed from point expressions and distances so the earlier
number-only expression contract is unchanged. Deletion cleans private
helpers and retains those shared by another owner; reload and undo keep IDs.

The existing Python DSL `Tangent(A,K)`, `Tangent(x,f)`, `Tangent(A,f)`,
`Tangent(l,K)` and `Slope(l)` lower through `from_construction`, including
reversed classic conic aliases. Formula-defined curves used by these tangents
are read independently. The native strict `line.tangent_conic_at` remains
in `opsWithoutClassic`: a general `Tangent(P,K)` must never become strict
from a single saved on-curve frame. The separate Commands grammar is unchanged;
its printer reports `unprintable_operation` for the five new operations.

Earlier `Tangent(Point,Circle)` and its by-value assignment are unchanged,
as is unsupported `Tangent(Circle,Circle)`. Arbitrary implicit/parametric
curves and other unsupported signatures refuse explicitly. Point/function
means tangent at x(P), with no external-point search. Infinite graph
derivatives are `not_differentiable`; vertical conic tangents remain valid.
Slope of a vertical line is `vertical_line`. A jump in `If` refuses a native
tangent where GeoGebra may use one branch; smooth joins, holes and poles
follow the documented native profile. No slope triangle is imported.

`tests/native/import/tangency/` contains synthetic source XML and unchanged
GeoGebra 5.4.936.0 archives. Their `ggb_tangency_*` scenes and shared fixtures
include changed inputs, undefined/recovery and explicit refusals. Direct XML
coefficient assertions and analytical curves independently check geometry.
Reproduce them with `python -m tests.native.ggb_tangency_fixtures [--check]`.

Reproduce the source archives, scenes and parity fixtures with
`python -m tests.native.ggb_expression_fixtures [--check]`. The four
`parity/v1/ggb/ggb_{point_expression,vector_expression,vector_rotate,expression_refused}.json`
files contain live input changes and, in their optional `import` section,
the source construction XML and expected report entries, including
`formula_unsupported` refusals. Source archives live in
`tests/native/import/expressions/`.

1.10.0a2 (`native.has("convert.formula")`): the arithmetic of numbers and
measures — 24 keys (`+ - * / ^`, the opposite, `Abs`, `Sqrt`, `Sin`, `Cos`,
`Tan`, `Ctan`, a copy) — is `number.expression`. The other 46 keys of
arithmetic (45 since 1.11.0rc1: `cpx_to_a` was no command, `mapVersion` 3)
stay `formula_unsupported`: they compute with points, vectors,
angles or segments (`number.expression` takes numbers only and gives a
number, not an angle). An argument that is an expression with no object of
its own — `Circle(A, r/2)`, `Circle(A, Distance(A, B))`, a command inside
a formula — is `formula_unsupported` with the expression in `detail` (a
document element of no report entry would be needed). After 1.11.0 the
arguments of `Translate`, `Segment`, `Line`, `OrthogonalLine`, `Vector`,
`Point`, `Intersect`, `Ray`, `Circle`, `Rotate`, `Polygon`, `Parabola`,
`ClosestPoint`, `Midpoint` and `PerpendicularBisector` (and conic equations)
keep such expressions as hidden, locked helpers outside `native_ids`; their
results are still value-checked. Since 1.14.0 every helper of the import
follows the rule of the helpers of marks of the web (1.0.55): no name,
`appearance` `{visible: false, locked: true, role: "aux", label: {mode: "none"}}`
and `elements.<id>.origin = {kind: "auto", source: <operation>}` — the
operation of the first imported object (in the order of the report) that
needs it; `native.edit.delete` removes a helper with that operation or hands
it to another operation that still reads it (kernel.md, `delete`). GeoGebra writes
`sqrt(a)`, `sin(a)` and `2a`, which the classic parser does not take
(`parse_error` in 1.10.0a2); `Sqrt(a)`, `Sin(a)` and `2*a` translate.

1.10.0a3 (`native.has("convert.ggb_expressions")`): the import reads the
expression of a number of a `.ggb` itself (`convert/ggb_expr.py`) where the
classic does not translate it — the classic parser is the behaviour of
`loadGGB` and is not changed (decision 3 of the tech lead). The reader
tokenizes the text and reads it by recursive descent into AST v1, nothing is
evaluated: `+ −` below `· /` and the implicit product (`2a`, `a b`,
`2(a + b)`, `1/2a` is `(1/2)·a`, left to right as in GeoGebra), then the
unary minus, then `^` (right-associative, `−a²` is `−(a²)`), then the
superscript powers (`a²`, `a⁻¹`) and `°`; the lowercase functions `sqrt`,
`abs`, `sin`, `cos`, `tan`, `asin`/`arcsin`, `acos`/`arccos`,
`atan`/`arctan`, `exp`, `ln`, `log` (natural; `log(b, x)` — to the base
`b`), `lg`, `cot`, `sec`, `csc`, the commands `Min`, `Max` of two numbers,
`π`, `ℯ`. A reference must be a `numeric` or an `angle` of the file that is a
number of the document; the formula is `number.expression` with these
references, its value is checked against the saved one (`value_mismatch` —
`differs`). An expression without references (`2π`) is a free number of its
saved value, as the classic makes of `sqrt(2)`. What stays outside says why
(`formula_unsupported`): a function the formulas do not have (`floor(a)`,
`round(a)`, `random()`), a command (`Distance(A, B)`), coordinates (`x(A)`),
an object that is not a number (a segment, a function, a list), a tree past
the limits of AST v1 (`expr.md` §2: depth, 256 nodes, an integer power above
64, a text longer than 1000 characters); a text the reader does not know
stays `parse_error`. A computation with points, vectors, angles or segments
the classic parsed keeps its reason of 1.10.0a2, and so does a formula of
the reader over an angle of a figure (`sin(γ)` of `γ = Angle(B, A, C)`). An
`angle` by an expression the classic did not parse: a constant (`2π/3`) is
the free angle of its saved value; one computed from objects (`2α`) is
`formula_unsupported` — `number.expression` gives a number, not an angle.

A point given by coordinates that are objects of the file (`P = (A1, B1)`)
was a free point at its saved place — it lost the dependency on the numbers,
a false `editable`. It is `picture`, `unsupported_signature` until L4 brings
the ops of points by coordinates; `Point(0.3, 0.2)` of literals (and of the
DSL, which passes the values of its variables) stays a free point.

`AngleBisector` — the name of the GeoGebra interface some files carry — is
`AngularBisector` for the import (`ggb.COMMAND_SYNONYMS`,
`native.has("convert.command_synonyms")`); the classic `loadGGB` reads the
file as it is.

Every op and free row has three cases in `tests/native/test_native_l5_convert.py`
(1.10.0a2): the general one, another configuration (the next variant of
each input — for a `byValue` row the classic outputs meet the slots in
another order, for an indexed row it is the other output) and a degenerate
one (well-formed inputs in a degenerate configuration: coincident or
collinear points, parallel lines, a tangency, a zero factor or vector).
Fourteen rows have no degenerate configuration the classic can reach, with
the reason (`NO_DEGENERACY`: a circle of radius 0 and a line through one
point are undefined in the classic; a free point; a locus is never
compared; a sum, a difference, the opposite, a copy, the sine and the cosine
are defined for every number). The 24 formula rows have the same three
cases (a division by zero, the root of a negative number, …). In 35
degenerate configurations the classic and the kernel
disagree — at a tangency the classic gives one point and the kernel a
double one; a zero factor, a zero vector of a ray, a regular polygon on
coincident points, a semicircle on coincident points, a point on a ray of
zero length are point-like in the classic and undefined in the kernel; the
bisectors of parallel lines are undefined in the classic, the kernel gives
the midline; a flat polygon has a centroid in the classic only; the classic
keeps the dimension of a measure (a length plus an area, a length plus a
number, a cube of a length are undefined there), the kernel has none. They are
`differs`, never `editable` (`DEGENERATE_DIFFERS`).

### GeoGebra function definitions

The GGB importer reads source function definitions independently of classic
parsing. A companion `<element type="function">` accepts a bare body in `x`,
`f(x) = body`, `f(t) = body`, or `y = body`; an explicit function header must
match its source label and have one formal variable. Each form may follow the
source label as GeoGebra saves a graph — `i: y = (-abs(x)) + 4` (since
1.14.0; before it was `parse_error`); the label of another object there is
`formula_unsupported`. Only variable nodes are
renamed to `x`: labels such as `t_1` remain distinct source objects.

The supported arithmetic and math functions are those of the number-expression
reader above. Functions additionally accept nested `If(condition, then[, else])`
and `If[condition, then[, else]]`, comparisons `< <= > >= ≤ ≥`, chained
comparisons, `&&`, `||`, `!`, and parentheses. Conditions are allowed only in an
If condition. Evaluation is lazy: unchosen branches and short-circuited
conditions are not evaluated. If without an else has no value where its
condition is false. Equality, inequality, CAS commands, lists, coordinates,
calls to source functions and unknown math functions remain unsupported.
The text is never executed, and existing expression work limits apply.

Each definition becomes `function.expr`, retaining numeric source objects as
ordered references, including live `number.expression` results. Equal current
values never merge two source objects or replace a named number with a literal.
An angle may be a reference only if its native element is a number with angle
units; an angle of a figure is not coerced to a number.

Ordinary functions omit `min` and `max`, giving domain `[null, null]`.
Saved view bounds, zoom, sampling and renderer bounds do not restrict the
mathematical domain. Formula operations can still be undefined at particular
values of `x`. The XML command `Function(inline_body, a, b)` retains explicit
finite literal bounds, evaluated safely from constant ASTs. A named numeric
bound, including a currently constant object or an expression referring to it,
is refused. Restricting an existing function object is also outside this subset.

Function report values have the form
`{"kind":"function","value":{"expr":AST,"refs":[numbers],"domain":[min,max]}}`.
`ggb_value` comes from the independently parsed source definition and saved
source numbers. Verification requires exact AST and variable normalization,
exact ordered source-to-native reference IDs, exact literal domain, and numeric
reference values within the existing import tolerance. Merely evaluating the
operation does not prove the definition was preserved. Missing source evidence
keeps `value_check: "not_checked"` and category `differs` with `value_unchecked`;
a mismatch gives `failed` and `value_mismatch`. This establishes preservation
within the supported source language, not equivalence to arbitrary GeoGebra
expressions. The GGB-specific reader does not extend `from_construction`, change
`dsl_map.json` promises, or add support for Root, Extremum or function intersections.

An XML `Point(f)` on an accepted function becomes `point.on_function`
(since `mapVersion` 6 also on a literal domain and on an `If` — a change of
the import: the operation is that of registry 1.6, its kernel unchanged, so
a registry 1.8 consumer evaluates it). Its finite saved abscissa (homogeneous `x/z`) is the free
`pathParameter` input; its ordinate is always recomputed from the function.
Changing a numeric reference changes the ordinate at the same abscissa, and
changing the path input changes both coordinates. Saved coordinates are checked:
a mismatching ordinate is `differs/value_mismatch`, never a free-point snapshot.
A pole gives native `out_of_domain`; undefined numeric ancestors propagate
`upstream`. Recovery recomputes values without retaining the last good position.
An undefined saved ordinate is acceptable when source `x` remains finite, but
an absent/non-finite abscissa is refused rather than invented as zero.

`Point(f,t)`, including literal `t`, and tuple points such as `(a,f(a))` or
`(1,f(1))` remain unsupported: they do not have a free native abscissa with the
same dependency and editing semantics. On an explicit restricted domain the
abscissa is clamped to its ends, as GeoGebra clamps the path parameter of a
function with an interval; on an `If` the point has no value in a gap
(`out_of_domain`) and the saved point checks the branch it lies on (a saved
point off the native branch is `differs/value_mismatch`). Dragging such a
point into a gap leaves it where it was (`native.drag`: `no_convergence`),
while GeoGebra may move it to the end of the piece; a point on an `If`
interval (`If(a ≤ x ≤ b, …)`) is not clamped to the interval by drag.

### Conic elements (registry 1.13, mapVersion 10)

`has("conic_elements")` announces five new operations: the owned circle
adapter, directrices, asymptotes, point polars and conjugate diameters.
The earlier center, focus, vertex and axis operations retain their signatures,
slot policies and minimum versions. Only the five additions belong to the
`conic_elements` module group.

| GeoGebra source | Native lowering |
|---|---|
| `Center(K)` | `conic.center`; actual native circle inputs use `point.center` |
| `Focus(K)`, `Vertex(K)`, `Axes(K)` | existing `conic.foci`, `conic.vertices`, `conic.axes` |
| `FirstAxis` / `MajorAxis` | `conic.axes`, bind only `focal` |
| `SecondAxis` / `MinorAxis` | `conic.axes`, bind only `conjugate` |
| `Directrix(K)` | `conic.directrices` |
| `Asymptote(K)` | `conic.asymptotes`; only hyperbolas have finite lines |
| `Polar(P,K)` | `line.polar_conic`, including circle inputs |
| `Diameter(d,K)` / `ConjugateDiameter(d,K)` | `line.conjugate_diameter`, line/vector inputs |

The importer captures source commands before classic parsing and retains raw
names, labels and numeric aN ordinals. Aliases do not require a classic
implementation. Safe inline point/vector formulas and quadratic equations
use the existing native AST language with live references; arbitrary nested
classic commands are not executed to recover an operand.

Subtype routing uses the actual native element type. Circle foci, vertices
and axes, including selectors, use a hidden, locked `conic.from_circle`
adapter whose output is always `conic`. Its element has `role: aux` and
`origin: {kind: auto, source: <owner operation ID>}`. Deletion cleans the
owned graph, shared dependencies survive with a new owner, and undo/reload
retain IDs. Center needs no adapter. Correct routing does not make an
undefined input circle defined; a saved finite center against an undefined
native circle remains an honest `differs/value_mismatch`.

Point and line groups bind injectively by saved value, prioritizing finite
matches, then explicit undefined evidence, then original ordinal. Points
use homogeneous coordinates; lines use normalized `[a,b,c]` with safe
scaling of overflowing norms and `tol.import`. Coincident circle foci occupy
the separate `first` and `second` slots. Coincident named saved lines in
distinct-line groups refuse the whole group with `unsupported_signature`.
The separate tangency multiplicity rule is unchanged. Missing coordinates
are `value_unchecked`, not evidence of undefined. Finite XML coefficients
remain line evidence even when an external app API would report undefined
under its own epsilon rules. Native/saved disagreement stays `differs`.

Empty `aN=""` labels create no element and do not shift following ordinals.
Named undefined outputs keep their slots and may recover. Repeated line
capacity is at least two and covers every raw ordinal, within 1…100; unused
slots follow `branch_absent` or the empty-set reason. Old conic parts do not
gain `found`; only the new repeated sets report it. A GeoGebra parabola's
second axis has no defined native conjugate slot and stays a mismatch rather
than becoming a fabricated perpendicular line.

Existing Python DSL Center/Focus/Vertex/Axes/MajorAxis/MinorAxis/Directrix/Polar
factories use the same lowering, including the classic reversed polar alias.
Asymptote, conjugate diameter and the representation adapter have no classic
dispatch key and remain in `opsWithoutClassic`; no factories are invented.
Scalars, line poles, function asymptotes and source segment/ray diameters
are explicit `unsupported_signature` refusals. The Commands grammar is
separate: new operations report `unprintable_operation` where it has no syntax.

Native frame signs and fixed ranks may differ from GeoGebra eigenvectors;
the saved-value matcher settles the import frame without promising identical
motion history. A fully undefined saved set is bound by its original output
ordinals; after movement, GeoGebra's order may differ because of the sign of
its own eigenvector. Native retains finite near-center polars and distant diameters
where GeoGebra may apply an absolute epsilon. Degenerate conics remain
undefined, even when GeoGebra continues algebraic parts.

`tests/native/import/conic_elements/` and `parity/v1/ggb/ggb_conic_elements_*`
contain synthetic sources and unchanged GeoGebra 5.4.936.0 archives, including
changed inputs, sparse outputs, recovery and direct saved-coordinate checks.
Reproduce them with `python -m tests.native.ggb_conic_elements_fixtures [--check]`.
Historical fixture registry labels stay frozen by `_fixture_registry.py`;
new documents declare their minimum required registry instead of relabeling
the whole corpus at every release.

## 2. Keys and IDs

`id = uuid5(id_namespace, key)`. Keys: a `.ggb` object — `ggb:<label>`; a DSL
variable — `dsl:<name>` (`key_of(name)` gives another key); a phantom `_N` —
`anon:<classic key>(<input keys>)#<output number>`, a repeat `~2`, `~3`: the
key follows the inputs, so a line inserted above changes no ID. An element —
`el:` + key (the second element of one object — `el:<key>/<slot>`); an
operation — `op:` + the key of its first output; `documentId` —
`uuid5(namespace, "document")` (the web replaces it). The names stay in
`bindings.legacyNames` and `displayName`.

## 3. Translation

Free objects first (a point → `point.free`, a number or slider →
`number.free` / `number.angle` with `min`, `max`, `step`), then the commands
in the classic order. A command whose input did not translate makes the
closure. Multi-output commands (intersections, tangents, bisectors of lines,
sector-line intersections) choose the slot of each classic output by value:
one evaluation of a probe document that binds every slot (decision 9; the
order of the classic is not static — C3). A point on a path gets its
`pathParameter` by `native.project` of its value. The document is validated
after every stage; an operation `validate` refuses is dropped with its
dependents.

## 4. `value_check` (tolerance `tol.import = 1e-6·S`)

| Type | `ggb_value` (from the XML) | Measure |
|---|---|---|
| point | `<coords x y z>` → `[x/z, y/z]` | distance |
| vector | `<coords x y z=0>` → displacement `[x, y]` | distance from the native displacement `b − a` |
| number, angle | `<value val>` (radians) | difference (an angle — on the circle; with `<angleStyle val="1|2">` the size shown within 0–180° / 180–360° is accepted too, `range` in `ggb_value`) |
| line, ray | normalised `<coords>` coefficients | coefficients |
| segment | the coefficients (the check); the two points in `ggb_value` when it is between two points | coefficients |
| circle, arc, sector | `<matrix>` → centre and radius | centre and radius |
| polygon | the vertices by label | vertices |
| other | — | `not_checked` |

`from_construction` compares with the classic values (`kernel/bridge.from_classic`).
Undefined in both (an intersection that does not exist) is `passed`.
The XML vector report value is `{kind: vector, value: [[0, 0], [x, y]],
components: true}`: only its displacement is saved, regardless of its
displayed start point. Without `components`, classic vector comparisons
still check both endpoints. Point and vector expressions with a value
different from the saved coordinates are `differs` / `value_mismatch`.

## 5. The report `import_report.v1`

Schema: `schema/import_report.v1.schema.json` (the master copy; the web's
draft plus additions). Every `<element>` of the XML is exactly one entry:

- `editable` — an op with `value_check = passed`, or a free input taken as is;
- `differs` — translated, the value does not match (`value_mismatch`, `delta`)
  or is not comparable (`value_unchecked`, `not_checked`: a locus — decision
  12, «zero falsely editable»);
- `picture` — not translated, a value the web can place still (a point, a
  segment between two points, a polygon, a text);
- `unsupported` — not translated, with a reason;
- `closure` — depends (through any chain) on an unsupported object
  (`depends_on_unsupported`); a dependent of a picture is a picture or
  `unsupported` with `depends_on_unsupported`.

Reasons: `no_registry_op`, `random_point`, `formula_unsupported` (an argument
is an expression: `detail` names it), `style_only`, `script`, `3d`, `cas`,
`spreadsheet`, `image`, `latex_macros`, `fixed_text`, `unsupported_signature`,
`list`, `macro`, `ui_object`, `parse_error`, `depends_on_unsupported`,
`value_mismatch`, `slot_ambiguous`, `value_unchecked`. An object with a GGB
script is `script` (the script is never run; its siblings of one command stay
editable); an object the classic froze (a command it cannot run, an
expression it cannot parse) is not editable.

Each entry also carries `command`, `signature`, `detail` (Russian), `ggb_value`,
`native_value`, `delta`, `label {visible, mode, caption?}`, `ggb_style` (keys
of `appearance.overrides` the classic `loadGGB` would give: colours 6-digit
hex, thickness / 2 px, point size × 2 px, exact dash sequences, the point shape,
`angle_range`, the decoration: `tick_count`, and since 1.13.0 a segment's arrows
4–6 as `parallel_count` 1–3, an angle's ticks 3–5 as `arc_tick_count` 1–3 and
its arrows 6/7 as `arrow_head` `end`/`start`), `hidden`, `layer`. The document carries `appearance.visible`
and `appearance.label`; layer order and value-label precision also use
`appearance.overrides`. The colours are the web's decision (decision 8).
`dropped`: `script` (a non-default global `ggbOnInit` too), `animation`,
`conditional_visibility`, `dynamic_color`, `layers`, `3d`, `cas`, `image`
with `names` (≤ 50). `warnings`: `{code, ggb_name?, detail?}`.
`document_hash` is `native.content_hash` of the document.
`report_problems(report, document)` checks the rules the schema cannot.

### Imported appearance and sliders

`lineStyle` types 0, 10, 15, 20 and 30 use the pixel sequences of
[GeoGebra's `EuclidianStatic.getStroke`](https://github.com/geogebra/geogebra/blob/main/source/shared/common/src/main/java/org/geogebra/common/euclidian/EuclidianStatic.java).
For width `w = thickness / 2`, the sequences are solid (`[]`),
`[4+w, 4]`, `[8+w, 8]`, `[w, 3]` and `[8+w, 4, w, 4]`.
`ggb_style.stroke_dash_pattern_px` is authoritative. Its 2 or 4 positive
lengths are style pixels; an empty array explicitly selects a solid stroke.
Unlike `stroke_dash_ratio` / `stroke_dash_period_px`, an explicit sequence
is never fitted to path ends or a closed circumference. SVG, PDF, EPS, TikZ
and the video camera use the same lengths. JSXGraph uses its nearest fixed
preset, including preset 6 for dash-dot. Ratio and period remain in the
report for older consumers; they approximate dash-dot. Unknown line styles,
and dashed polygon/angle/sector outlines unsupported by the renderer, have
`line_style_unsupported` warnings.

If any object has a nonzero layer, imported drawn elements receive separate
`z_index`, `z_index_fill` and `z_index_label` values, with 100 native z units
between consecutive GeoGebra layers. This places every fill, outline and
label above the previous layer. Invalid layers and layers of untranslated
objects remain `dropped: layers`; translated layers do not.

Label modes 0–3 map to `name`, `name_value`, `value` and `caption`.
Scalar values of segments, vectors, polygons and angles remain live and
use the file's decimal precision. Dynamic captions referencing GeoText keep
that text's current displayed value as a static `caption`, including hidden
text sources and texts without a native anchor. The same saved-value text
evaluation and conservative TeX checks as editable text import apply.
A caption in label mode 3 whose text refers to no object (string literals
only, no `%n`/`%v`/`%x`/`%y`/`%z`) is constant: its snapshot is exact, the
element stays `editable` and there is no warning. Visible frozen captions of
other texts have `label_caption_simplified` warnings and keep their live geometry, while their report entries are `differs` with reason
`value_unchecked`, `value_check: not_checked` and the explicit detail
that the caption does not recompute. They count as `simplified` in audits.
Missing/unknown text expressions, unsupported TeX commands (including file
access) and control characters hide the caption with a specific
`label_caption_unsupported` reason. Hidden captions remain hidden without
simplifying their geometry. Coordinate/equation labels, caption+value
(mode 9) without a resolved dynamic caption, and `%n`/`%v`/coordinate
caption substitutions also have explicit warnings and a hidden label.
Visibility is retained. `labelOffset` becomes `label.offsetWorld`, divided
by the source view's x/y scales with its screen Y inverted. A missing or
invalid scale has `label_offset_dropped`; the displacement is relative to
the native label anchor, not a claim of pixel-identical GeoGebra placement.

Numeric slider bounds come from `<slider min max>` and their step from
`<animation step>` (the legacy `slider step` is also accepted). Numeric
literal bounds and positive steps go to `number.free` / `number.angle`.
Dynamic, nonfinite or inconsistent bounds and invalid steps have
`slider_range_dropped`; the saved number remains editable without these
constraints. Native number operations retain a step for UI consumers and
clamp to bounds; they do not quantize values. The slider bar and its label
are not drawn and have `slider_display_dropped`. No timeline is synthesized:
`playing=true` is `dropped: animation`, while
`animation_settings_dropped` lists playing, speed, type and step even for
a paused animation.

Consumers must accept the new explicit dash sequence and label z key, and
retain layer/precision overrides when choosing their own colours. The web
integration needs its generated style contract and its validation/semantic
key lists updated together; older consumers can only use the ratio fallback.

`ggb_value` of a text (1.10.0a2, `native.has("import_report.text_template")`)
is `{kind: "text", text, anchor, anchor_ref?, screen?, template?, refs?,
decimals?, shown?}`:

- `text` — the GeoGebra expression (a literal without its quotes);
- `anchor` — `[x, y]` of every text that has a place: its start point, the
  saved position of the point it is attached to (`anchor_ref` — that point's
  name), or a text fixed on the screen — its pixel in drawing coordinates
  (`screen: true`); `null` — no place in the file;
- `template`, `refs`, `decimals` — for a text that is a `+` of literals and
  objects: the template of `text.free` (`{k}` — item `k` of `refs`, the
  braces of a literal doubled) and its references `{ggb_name, as}`, where
  `as` is what GeoGebra prints: `point`, `number`, `angle` (degrees),
  `length` (of a segment: `measure.length`), `area` (of a polygon:
  `measure.area`); `decimals` — the rounding of the file. A part that is not
  such an object (`x(A)`, a function, a command) — no template;
- `shown` — the text as the file shows it, from the saved values (the
  classic `resolve_text_string` gives the same).

The importer builds `text.free` for supported literal/reference concatenations.
The anchor is `anchor_ref` or a hidden fixed point at `anchor`; segment lengths,
polygon areas and geometric angles use hidden measure operations. A text becomes
`editable` only when its evaluated string and anchor match the saved values.
Ordinary TeX becomes native inline math, including `\[...\]` as
`$\displaystyle ...$`; literal braces survive template escaping. Unknown user
macros, unsupported expressions or delimiters remain `picture` with a reason
and detail. Visibility is retained. The web may build remaining supported text
templates from the report after its own value check.

`depends_on` of every object names the objects of the file its definition
refers to outside the string literals (1.10.0a3,
`native.has("import_report.text_literals")`): the letters of the LaTeX
formula of a fixed text (`"$S = \frac{1}{2} a h_a$"`) are no references, so
such a text has no `depends_on` and a template without references (`refs`
`[]`); `"S = " + a` keeps `depends_on` `["a"]`. A name with an index in
braces (`t_{AB}`) is one name.

`seq` of the operations follows the construction protocol (the XML order);
`steps` (groups) appear only when the XML has breakpoints — a step is the
protocol up to a breakpoint inclusive, the rest is the last step.
If a damaged file interleaves dependencies so these groups form a step
cycle, the import keeps the geometry, omits the conflicting explicit groups
and reports `protocol_steps_dropped`. `native.steps` then orders individual
operations by their dependencies (1.11.0rc13).

## 6. Untrusted input (plan §7)

A `.ggb` is data. `from_ggb` refuses before parsing (`native.ImportRefused`,
`.code`): `import_too_large` (file 20 MB, 50 entries, 50 MB unpacked by the
headers and by a bounded read — a zip bomb with lying sizes too, XML 10 MB),
`import_not_ggb` (not a zip, no `geogebra.xml`), `import_too_many_objects`
(3000), `ggb_invalid` (a `DOCTYPE` or `ENTITY`, XML deeper than 64, broken
XML). The archive is read in memory, nothing is extracted. GGB scripts are
counted, never run. The classic parser turns GGB expressions into Python for
`dsl.run`; `ggb_parser._check_ggb_code` now refuses there anything but one
assignment of an expression — no `__dunder__` name, no private attribute, no
lambda, comprehension or definition (before 1.10.0a1 a `.ggb` expression
could reach `object.__subclasses__()`). `tests/native/test_native_no_exec.py`
keeps `exec`, `eval`, `compile`, `subprocess`, … out of `animageo.native`.

1.10.0a2, after fuzzing (`tests/native/test_native_l5_fuzz.py`, marker
`fuzz`; the random series are `slow` too): the outcome of any input is a
report or `ImportRefused` — never another exception, never a hang (each case
runs under a 20 s deadline). What the fuzzing changed:

- refusals: any damage of the archive (a broken deflate stream, an unknown or
  encrypted method, a wrong CRC) is `import_not_ggb`; a `DOCTYPE` is refused
  in any encoding (UTF-16/32 too, by the parser, not by a byte search); an
  encoding Python cannot decode is `ggb_invalid`; an object name longer than
  200 characters is `ggb_invalid`;
- a regular polygon takes 3 to 100 vertices (`unsupported_signature`
  otherwise); the classic `Polygon(A, B, n)` refuses more than 10 000;
- a name defined twice: the first definition wins, the second — a command,
  an expression or an `<element>` — is the warning `duplicate_definition`;
  an output of a command without its own
  `<element>` is not an object of the report, its dependents are
  `parse_error`;
- a free input whose value fails the check (a point at infinity, a
  non-finite value) is `differs`, not `editable`; a view with non-finite or
  empty bounds is ignored;
- the categories are set dependencies first and then settled
  (`report.settle`): the closure is exactly the dependents of unsupported
  objects, and an editable object never refers to an element that is not in
  the document — whatever the order of the XML, a cycle or a dangling name;
- the long strings of the report are cut to the schema (`signature` 80,
  `app` and `ggb_version` 40).

## 7. Command line

```text
python -m animageo.native from-ggb <file.ggb> [-o doc.json] [--report rep.json] [--namespace UUID] [--mode partial|strict]
python -m animageo.native convert map [--check] [--coverage <dir> [--json]]
python -m animageo.native convert corpus record|verify <dir> [--expected <dir>]
```

`from-ggb`: exit 0 (`partial`, even with objects that do not translate), 1 —
`strict` with objects that are not editable, 2 — a refused or missing file.
Without `--namespace` the IDs come from the sha256 of the file.

### Import audit

```text
python -m animageo.native import-audit <paths…> [--weights FILE] [--json OUT] [--web-registry X]
```

`import-audit` (`convert/audit.py`) imports every `.ggb` file of the paths (a
directory — its `*.ggb` files recursively) as `from-ggb` does without
`--namespace` and prints one line of totals, and with `--web-registry X` a
second one (see below). With map version 7 and `--web-registry 1.9`, the
weighted corpus of 221 files gives:

```text
library files 221 full 209 objects 4885 editable 4850 lost 14 picture 20 differs 1 value_unchecked 1
web at registry 1.9 files 221 full 206 objects 4885 editable 4839 lost 18 picture 27 differs 1 value_unchecked 1
```

The examples directory, with unit weights (149 files), gives:

```text
library files 149 full 122 objects 4875 editable 4647 lost 139 picture 74 differs 15 value_unchecked 14
web at registry 1.9 files 149 full 118 objects 4875 editable 4539 lost 207 picture 115 differs 14 value_unchecked 14
```

Applying the same corpus weights to examples counts one 42-object file
twice (150 weighted files): library editable 4689, web editable 4581;
lost, picture and differing counts stay the same. Compared with 1.14.0,
the library gains 11 editable objects in the weighted corpus and 108 in
unit-weighted examples. A consumer on registry 1.9 cannot recompute the
new expression operations yet.

- `files` — the files, each counted with its weight: `--weights` is a JSON
  object `{sha256: count}`, a file not listed counts once;
- `objects`, `editable`, `picture`, `differs` — the entries of the reports
  by category; `value_unchecked` — the part of `differs` with that reason;
  `lost` — `unsupported` + `closure`;
- `full` — a file with a document and without lost, picture or differing
  objects and without `dropped` kinds; a refused file counts in `files` only
  (`refused N`); a file whose import fails with an exception is `errors N`
  and the exit code is 1.

`--web-registry X` adds the line `web at registry X` of a consumer that knows
the registry up to `X`: an operation whose `since`, or the `familySince` of a
type in one of its family slots, is newer than `X` is not recomputed there. An
editable or differing object it produces, or built on a hidden helper it
produces, is a `picture` (`web_capability_missing`); the editable and
differing objects that depend on it (`depends_on`, any chain) are `closure`.
`--json OUT` writes `animageo.import_audit` v1: `totals` (`library`, `web`)
and a row per file — `path`, `sha256`, `weight`, `outcome` (`report`,
`refused` or `error` with `code`), the counts, `dropped`, `elements`
(`[name, type, category, reason, command, signature]`) and `web` (the counts
and `changed`: `[name, category, reason]` of the objects the filter moved).

## 8. Corpus and expectations (1.10.0a2)

`convert corpus record <dir>` writes for every `*.ggb` under `<dir>`
(recursively) the expectation `<expected>/<sha256>.json`
(`animageo.import_expectation` v1, `convert/corpus.py`): the outcome — a
report or a refusal with its code —, whether there is a document, the
summary, the dropped kinds, the warning codes and `[name, category, reason]`
of every object, one per line. No IDs and no values: a change of the
document that keeps the categories keeps the expectation. `verify` compares
(exit 1): a file without an expectation, another outcome, category or reason,
a report that breaks `report_problems`. `--expected` defaults to
`tests/native/import/expected`, where the expectations live in git (the
files of a real corpus do not: other people's work); an expectation changes
only with its reason in the commit message.

`convert map --coverage <dir>` counts the objects of the corpus by category
and by key — the `dsl_map` key of a translated command, else
`command:<GGB command>`, else `type:<GGB type>` (free objects); `--json`
prints the same as JSON with `editable_share`.

The deliberate files `tests/native/import/synthetic/*.ggb` (24: 3D, CAS,
spreadsheet cells, scripts and a button, lists, a macro, breakpoints, a DTD,
a zip without `geogebra.xml`, pictures only, texts, a function and its
closure, an expression argument, dropped effects, a random point, styles,
user-interface objects, regular polygons; 1.10.0a3: numbers by the
expressions GeoGebra writes, a fixed LaTeX text with names in its formula,
`AngleBisector`) are the output of
`tests/native/ggb_synth.py` (`python -m tests.native.ggb_synth` rewrites
them; a test compares them entry by entry), each shows what it is for
(`test_native_l5_corpus.py`), and their expectations are in
`tests/native/import/expected/`.

Speed (`test_native_l5_speed.py`, `slow`, the numbers are printed): a file
of 3000 objects (the limit; groups of a triangle with its midpoints, medians,
centroid, a circle, a perpendicular and the medial triangle, all editable)
imports in 4.0 s against the budget of 30 s; `from_construction` of a scene
of 300 operations takes 0.1 s against 1 s.

Style witness (`test_native_l5_style_witness.py`, `slow`, manim): ten files
(the six real ones and four deliberate) are drawn by the classic `loadGGB`
and by `native.render` of the document with `ggb_style` as
`appearance.overrides`; the objects that do not translate are hidden in the
classic drawing. The SVGs are compared by features, not pixels: the multiset
of strokes (colour, width in pixels, opacity, dash) and fills (colour,
opacity) of the paths is the same. The witness found that a shape without
fill (alpha 0) lost its fill keys and was drawn with the default fill of the
style; `ggb_style` now carries `fill_opacity` 0, and
`test_native_l5_ggb.py` compares `ggb_style` with the classic
`elem.ggb_style` key for key.


Registry 1.11 uses map version 8. Its function-analysis catalog lists
`function.roots_polynomial`, `function.extrema_polynomial`, `function.value`,
`function.root_near`, `function.root_interval`, `function.roots_interval` and
`function.extrema_interval` in `opsWithoutClassic`, so both directions of the mapping remain explicit.
This metadata does not add GeoGebra Root/Extremum source translation or change
any existing classic command row. All seven native operations and their analytical
fixtures can be used independently of that later import work.
