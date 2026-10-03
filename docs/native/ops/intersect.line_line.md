# `intersect.line_line` — intersection of two linear objects

Registry 1.0 (rays since 1.1) · group `intersect` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: linear`, `second: linear` (`linear` = `line` \| `segment` \| `ray`) |
| outputs | `point: point` |
| undefined | `parallel`, `coincident`, `outside_part`, `zero_length`, `upstream` |
| checks | `incident_both` |

## Carriers

Each input is turned into a carrier `(p, dir, L)`, `first` before `second`:

- `line {p, dir}` → `p`, `dir`, no `L`;
- `ray {origin, dir}` → `p = origin`, `dir`, no `L`, a ray (registry 1.1);
- `segment {a, b}`:

      dx = bx − ax
      dy = by − ay
      L  = hypot(dx, dy)
      if L ≤ tol.decide:        → undefined, reason "zero_length"
      p = a,  dir = (dx / L, dy / L)

The first slot that fails decides the result.

## Value

`u × v = ux·vy − uy·vx`.

    cr = d1x·d2y − d1y·d2x
    wx = p2x − p1x
    wy = p2y − p1y
    if |cr| ≤ 1e-10:                          (tol.decide, dimensionless)
        dist = |wx·d1y − wy·d1x|
        dist ≤ tol.decide → undefined "coincident", else undefined "parallel"
    t = (wx·d2y − wy·d2x) / cr
    x = p1x + t·d1x
    y = p1y + t·d1y
    for slot in (first, second):
        when the input is a ray:
            s = (x − px)·dirx + (y − py)·diry    (its carrier)
            if s < −tol.decide:
                → undefined "outside_part", detail {"slot": slot}
        when the input is a segment:
            s = (x − px)·dirx + (y − py)·diry    (its carrier)
            if s < −tol.decide or s > L + tol.decide:
                → undefined "outside_part", detail {"slot": slot}
        (the first slot outside its part decides)
    point = {x, y}

An intersection exactly at a segment end or at the origin of a ray is inside
the part.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` (per segment input) | `L` | `tol.decide` (length) |
| `parallel` | `cr` | `1e-10` (dimensionless) |
| `coincident` (only when parallel) | `dist` | `tol.decide` (length) |
| `outside_part` (per segment input, until the first outside) | `s` and `s − L` | `tol.decide` (length) |
| `outside_part` (per ray input, until the first outside) | `s` | `tol.decide` (length) |

## Checks

- `incident_both`: `max(dist1, dist2)` where `dist_i = |(x − p_ix)·d_iy − (y − p_iy)·d_ix|`
  is the distance to the carrier line of input `i`.
