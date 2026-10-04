# `circle.incircle` — inscribed circle of a triangle

Registry 1.3 · group `circle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `c: point` |
| outputs | `circle: circle`, `center: point`, `touch_a: point`, `touch_b: point`, `touch_c: point` |
| undefined | `collinear_points`, `upstream` |
| checks | `tangent_sides` |

The circle inscribed in the triangle `abc`, its centre and the three points
where it touches the sides: `touch_a` on the side `bc` (opposite `a`),
`touch_b` on `ca`, `touch_c` on `ab`. A document may bind any subset of the
outputs. GeoGebra `Incircle(A, B, C)`; the touch points are
`ClosestPoint(side, I)`.

## Value

    La = hypot(bx − cx, by − cy)
    Lb = hypot(cx − ax, cy − ay)
    Lc = hypot(ax − bx, ay − by)
    Lmax = max(La, Lb, Lc)
    if Lmax ≤ tol.decide:          → all slots undefined "collinear_points"
    cr = (bx − ax)·(cy − ay) − (by − ay)·(cx − ax)
    h  = |cr| / Lmax
    if h ≤ tol.decide:             → all slots undefined "collinear_points"
    p = La + Lb + Lc,  s = p / 2
    o = ((La·ax + Lb·bx + Lc·cx) / p, (La·ay + Lb·by + Lc·cy) / p)
    circle = {c: [ox, oy], r: |cr| / p}
    center = {x: ox, y: oy}
    ta = (s − Lb) / La,  touch_a = b + ta·(c − b)
    tb = (s − Lc) / Lb,  touch_b = c + tb·(a − c)
    tc = (s − La) / Lc,  touch_c = a + tc·(b − a)

`h` is the smallest height of the triangle, so every side is longer than
`tol.decide` once `h` is: the divisions are safe. `s − Lb` is the tangent
length from `b`, `s − Lc` from `c`, `s − La` from `a`. The result does not
depend on the orientation of `abc`.

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `collinear_points` | `Lmax` | `tol.decide` (length) |
| `collinear_points` | `h` | `tol.decide` (length) |

## Checks

- `tangent_sides`: for each side line, the largest of
  `| dist(c, side) − r |`, `dist(touch, side)` and `| hypot(touch − c) − r |`;
  and `hypot(center − c)`; infinite when a side has no length
