# `locus.of_point` — locus of a point

Registry 1.5 · group `locus` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `trace: point`, `mover: locus_driver` (`point` or `number`) |
| outputs | `locus: locus` |
| undefined | `unsupported_signature` (state `unsupported`), `not_dependent`, `empty_range`, `upstream` |
| checks | `on_trace` (sampled) |

The curve the point `trace` draws while `mover` runs over its whole range.
The value `{points: [[x, y] | null, …], range: [t0, t1], closed}`: `points`
are lengths, `range` scalars, `closed` compares exactly; a `null` sample is
compared exactly. `locus` is not in the families `path`, `curve` or `linear`
(a point on a locus and intersections with it are L4).

## Value

1. **Mover.** A `point` mover must be the point of `point.on_path`; a `number`
   mover the number of `number.free` with both params `min` and `max`.
   Anything else (a free point has no one-dimensional range) →
   `unsupported/unsupported_signature`.
2. **Dependence.** The producer of `trace` must be a dependent of the
   producer of `mover` (the mover itself counts), else `not_dependent`.
3. **Range** from the definition, not from the mover's position:

   | mover on / mover | `[t0, t1]` | closed |
   |---|---|---|
   | segment, arc | `[0, 1]` | no |
   | polyline (`n` vertices) | `[0, n − 1]` | no |
   | circle | `[0, 2π)` | yes |
   | polygon (`n` vertices) | `[0, n)` | yes |
   | sector | `[0, 3)` (the whole boundary) | yes |
   | line, ray | where `o + t·v` (the path frame of the producer, `kernel.md` §5.5) enters and leaves the window `B4`; a ray from `max(t_in, 0)` | no |
   | number | `[min, max]` | no |

   `B4` is `viewDefaults.bounds` (or the default bounds) scaled 4 times about
   its centre: `cx = (xmin + xmax)/2`, `hw = (xmax − xmin)·4/2`, the same in
   y. The clip is Liang–Barsky per axis (`v = 0` and `o` outside → no
   range): `a = (min − o)/v`, `b = (max − o)/v`, swapped when `a > b`;
   `t0 = max(a_x, a_y)`, `t1 = min(b_x, b_y)`. No range, or
   `(t1 − t0)·|v| ≤ tol.decide` → `empty_range`; for a number
   `t1 − t0 ≤ tol.decide` (scalar) → `empty_range`.
4. **Samples** `N = 256`, `k = 0 … N − 1`, with `span = t1 − t0`:

       open:    t_k = t0 + (k·span) / (N − 1)
       closed:  t_k = t0 + (k·span) / N

5. At every `t_k` the input of the mover becomes `{kind: "pathParameter",
   value: t_k}` (or `{kind: "number", value: t_k}`) and only the operations
   that depend on the mover **and** that the trace depends on are evaluated
   again, in the evaluation order, by the rules of `kernel.md` §5.2 (an input
   that is not defined makes the outputs not defined); the other values are
   those of the evaluation. `points[k]` is `[x, y]` of the trace or `null`.
   The document and the mover's input do not change. The decisions of the
   sampled operations are reported like those of any operation, so the
   fixture generator refuses a scene whose sample lies near a boundary.
6. Breaks are not cut by the kernel. Drawing (the renderer, the canvas)
   breaks the line between neighbouring samples when one of them is `null`
   or they are more than `0.25·S` apart; a closed locus also joins its last
   sample to the first by the same rule.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `empty_range` | `(t1 − t0)·|v|` (line, ray) | `tol.decide` |
| `empty_range` | `t1 − t0` (number) | `tol.decide` scalar |
| any | the decisions of the sampled operations | theirs |

## Checks

- `on_trace` (sampled): at `k = 0, N/4, N/2, 3N/4` the document is evaluated
  in full with the mover input at `t_k`; the error is the distance between
  that trace and `points[k]` (`∞` when exactly one of them is not defined).
  It checks the subgraph evaluation against the full one.
