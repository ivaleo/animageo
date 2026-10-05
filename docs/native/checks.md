# `animageo.native` — checks, relations and `general_position`

`native.check(doc, checks=None, *, inputs=None, relations=None, trials=0,
seed=None) → CheckReport` (since 1.8.1a4). The report has three maps keyed
alike:

| field | value |
|---|---|
| `results` | key → `passed` \| `failed` \| `inconclusive` \| `unsupported` |
| `errors` | key → the measured error `e ≥ 0` (absent when nothing was measured) |
| `details` | key → a reason (`{"reason": …}`) or a trial summary (below) |

`report.ok` is true when no result is `failed`. The browser kernel repeats
this page; the reference values are the library's.

## 1. Mandatory checks

Every registry operation that ran, gave a value for each result slot and
whose every element is `defined` gets the checks of its record
([kernel.md §5.3](kernel.md)). Key `"<operationId>:<checkId>"`; `checks`
limits the report to such keys or bare check IDs. An error `e` (a length)
is classified by `tol.check`: `e ≤ 1e-9·S` → `passed`, `e ≥ 1e-6·S` →
`failed`, otherwise or non-finite → `inconclusive`. The formulas are in the
op pages (`ops/<op>.md`, section «Checks»).

An operation with several slots is checked only when all of them are
defined: `intersect.line_sector` with a convex sector rarely is (a line
meets its boundary twice), a reflex sector can give all four points.

## 2. Relations

`relations` is a list of `{"id": string, "predicate": string, "args":
[elementId, …]}` with unique non-empty IDs; anything else is a caller error
(`ValueError`). Report key: `"relation:<id>"`.

The error of a relation is a length measured from the values of its
arguments in the evaluated document and classified like a mandatory check.
`S` is the scene scale; `d` a unit direction (`dir` of a line or a ray,
`(b − a)/|b − a|` of a segment or a vector); the carrier line of a linear
element passes through `p` (line), `origin` (ray) or `a` (segment, vector).

| predicate | args | error `e` |
|---|---|---|
| `incident` | a point and a `path` element, either order | `distance_to_path(point, path)` — the clamped part of a segment or ray, the sides of a polygon, the links of a polyline, the arc itself, the boundary of a sector |
| `parallel` | two of `linear` or `vector` | `abs(d1 × d2)·S` |
| `perpendicular` | two of `linear` or `vector` | `abs(d1 · d2)·S` |
| `equal_length` | two of `segment`, `vector` | `abs(length1 − length2)` |
| `equal_angle` | two `angle` | `abs(size1 − size2)·S` |
| `collinear` | three or more points | the two farthest points `P_i`, `P_j` (first pair on a tie) give the line; `e = max abs((P − P_i) × u)`, `u = (P_j − P_i)/hypot(P_j − P_i)`; all points within `tol.decide` of each other → `e = 0` |
| `concyclic` | four or more points | the triple of the largest `abs((B − A) × (C − A))` (first on a tie) gives the circle `(O, r)`; `e = max abs(hypot(P − O) − r)`; the triple's longest side `≤ tol.decide`, or its area over that side `≤ tol.decide` → `inconclusive` (`degenerate`) |
| `concurrent` | three or more `linear` | the pair with the largest `abs(d_i × d_j)` meets at `X`; `e = max` distance from `X` to each carrier; that cross `≤ tol.decide` (dimensionless) → `inconclusive` (`parallel`) |
| `tangent` | a `linear` and a `circular` element, or two `circular` | line: `abs(abs((c − p) × d) − r)`; circles: `min(abs(D − (r1 + r2)), abs(D − abs(r1 − r2)))`, `D = hypot(c2 − c1)` |

Statuses besides `passed`/`failed`:

- `unsupported` — `{"reason": "unknown_predicate"}`, `"type"` (an argument
  type outside the table), `"arity"` (wrong count) or `"dangling_ref"`
  (`elementIds` lists the missing ones). The types decide before the states:
  a relation of wrong types stays `unsupported` when an argument is undefined;
- `inconclusive` — `{"reason": "undefined", "elementIds": […]}` when an
  argument is not `defined`, `"zero_length"` for a direction of a segment or
  vector shorter than `tol.decide`, `"degenerate"`, `"parallel"` (above), or
  an error between the check thresholds (no reason then).

## 3. `general_position`

With `trials = N > 0` every mandatory check and every supported relation is
measured again in `N` trials, each a fresh evaluation with perturbed free
inputs; the case `inputs` stay the base of the perturbation.

**Generator.** SplitMix64 over unsigned 64-bit integers:

    state = state + 0x9E3779B97F4A7C15             (mod 2^64)
    z = (state ^ (state >> 30)) · 0xBF58476D1CE4E5B9
    z = (z ^ (z >> 27)) · 0x94D049BB133111EB
    next = z ^ (z >> 31)
    random = (next >> 11) / 2^53                    in [0, 1)

Seed `0` gives `0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4, 0x06C45D188009454F`.
Each relation has its own sequence, seeded by the first 8 bytes (big-endian)
of `sha256(utf8(m + "\0" + id))`, `m` = `str(seed)` when given, else the
`documentId`; all mandatory checks share the sequence of `id = ""`.

**One perturbation** draws, for the free inputs in element ID order (the
element of the first output slot of each free op):

| input kind | draws | value |
|---|---|---|
| `point` `(x, y)` | `u1`, `u2` | `ρ' = ρ·sqrt(u1)`, `φ = 2π·u2`, `(x + ρ'·cos φ, y + ρ'·sin φ)` |
| `pathParameter` `t` | `u` | finite range `[lo, hi]` of the path: `lo + u·(hi − lo)`; otherwise `t + (2u − 1)·ρ/hypot(v)` (`v` the affine frame vector; `1` in place of `hypot(v)` when it is unknown), raised to `lo` when below; `branch` kept |
| `number` `v` | `u` | `min + u·(max − min)` when both bounds are params and `max ≥ min`; otherwise `v·(1 + (2u − 1)/4)`, or `(2u − 1)/4` for `v = 0` |
| `angle` | `u` | `2π·u` (also when the input is absent) |

An input without a value in the document (other than `angle`) draws nothing.
Ranges (`paths.parameter_range`): segment and ray as clamped, circle
`[0, 2π]`, polygon `[0, n]`, arc `[0, 1]`, sector `[0, 3]`, polyline
`[0, n − 1]`; a line has none.

**Trials.** `ρ = 0.25·S` (the base scale). In each trial the inputs are
perturbed and the document evaluated; a key that cannot be measured (its
operation or an argument undefined, or an evaluation error) is retried
within the same trial with `ρ/2`, up to 3 times, the other keys keeping the
first measurement; still unmeasured, it counts as `undefined`.

**Aggregate** of the base status and the `N` trial statuses:

- any `failed` (the base included) → `failed`, with the first counterexample;
- otherwise any `undefined` or `inconclusive`, or a base other than
  `passed` → `inconclusive`;
- otherwise `passed`.

`details[key] = {"trials": N, "passed", "failed", "inconclusive",
"undefined": counts, "counterexample"?: {"trial": k, "error": e, "inputs":
{elementId: input}}, "base"?: <the base detail>}`; a counterexample of the
base itself is `{"trial": 0, "error": e}`. An `unsupported` relation is not
tried and keeps its reason.

The same document, inputs, relations, `N` and `seed` give the same report
in both kernels, bit for bit up to the evaluation itself.
