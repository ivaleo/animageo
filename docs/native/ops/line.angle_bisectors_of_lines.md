# `line.angle_bisectors_of_lines` — bisectors of the angles between two lines

Registry 1.4 · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: linear`, `second: linear` |
| outputs | `internal: line`, `external: line` |
| policy | `bisector_kind` |
| orientation | `d1_plus_d2` |
| undefined | `zero_length`, `parallel`, `coincident`, `upstream` |
| checks | `equal_angles` |

Both bisectors of the angles between two lines (policy `bisector_kind`):
`internal` has the direction `normalize(d1 + d2)` of the unit carrier
directions, `external` is `internal` turned by +90°. For parallel lines the
slot whose direction sum is not zero is the midline; the other slot is
`parallel`, or `coincident` for one line. The classic
`angular_bisector_ll` returns the acute bisector first — the native order
follows the directions (a note for the L5 importer).

## Value

    c1 = carrier(first),  c2 = carrier(second)      (zero_length)
    cr = d1 × d2,  q = d1 · d2
    if |cr| > tol.scalar:
        X = intersection of the carriers
        q ≥ 0: i = (d1 + d2) / |d1 + d2|
        q < 0: w = d2 − d1,  σ = sign(cr),  i = (σ·wy, −σ·wx) / |w|
        internal = line through X with i;  external = line through X with (−iy, ix)
    else:
        h = (p2 − p1) × d1;  absent = "coincident" if |h| ≤ tol.decide else "parallel"
        M = p1 + (p2 − p1) / 2;  mid = line through M with d1
        q > 0: internal = mid, external = absent
        q < 0: internal = absent, external = mid

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `parallel` | `cr` | `tol.scalar` |
| `coincident` | `h` | `tol.decide` |

## Checks

- `equal_angles`: `max(|(d1 − d2)·i|, |(d1 + d2)·e|)·S`
