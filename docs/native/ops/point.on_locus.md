# `point.on_locus` — a locus point with a dependent parameter

Registry 1.10 · group `point` · beta · see [kernel.md](../kernel.md) §17.5.

| | |
|---|---|
| inputs | `locus: locus`, `parameter: number` (a reference or a literal) |
| outputs | `point: point` |
| undefined | `empty_locus`, `degenerate_locus`, `discontinuous`, `upstream` |
| checks | `on_path` |

GeoGebra `Point(locus, t)`: the parameter is clamped to `[0, 1]` and
interpolates the sample index, with the same rule as
[`point.on_path`](point.on_path.md#a-locus-registry-110). A closed locus
includes its closing link. The parameter is a fraction of the number of
links, not arc length and not the parameter in `locus.range`.

This operation has no free input: it follows its numeric argument. A
reference to a number remains a dependency when importing `Point(locus, t)`;
a literal remains fixed. A draggable glider, GeoGebra `Point(locus)` without
the second argument, uses `point.on_path` with the family `path` instead.

Empty samples give `empty_locus`; no nonzero link within a continuous run
gives `degenerate_locus`; a parameter in a break gives `discontinuous`.
The check measures distance to the same continuous runs used by projection.
