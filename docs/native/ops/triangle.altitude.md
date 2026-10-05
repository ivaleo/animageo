# `triangle.altitude` — altitude of a triangle

Registry 1.5 · group `triangle` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `vertex: point`, `side: linear` (record field `ends`) |
| outputs | `altitude: segment`, `foot: point`, `extension: segment` |
| undefined | `zero_length` (slot `altitude`; all slots for a side segment of zero length), `branch_absent` (slot `extension`), `upstream` |
| checks | `perpendicular`, `on_carrier` |
| orientation | `vertex_to_foot` |

The altitude from `vertex` to the carrier of `side`, its foot and, when the
foot falls outside the side, the extension of the side up to the foot. A pair
of points `BC` in «Команды» (`Высота(A, BC)`) becomes a hidden
`line.by_points(B, C)` (the slot is `linear`), whose ends are `B` and `C`.

## Value

    carrier p0, d of side — exactly as point.projection (the same function):
      segment: p0 = a, d = (b − a)/|b − a| (|b − a| ≤ tol.decide → all slots "zero_length")
      line: p0 = p, d = dir;  ray: p0 = origin, d = dir
    t = (V − p0)·d                       (V = vertex; x and y summed in this order)
    H = p0 + t·d                         bit for bit point.projection(V, side)
    h = |V − H|
    h ≤ tol.decide  → altitude "zero_length"; foot stays defined
    altitude = {a: V, b: H, length: h}
    ends of the side: a segment — a, b; a line or a ray — the two defining points
      of its producer frame (line.by_points: a, b; ray.by_points: origin, through;
      the frame rule o = args.Y, v = args.X − args.Y of _types.json); other lines
      and rays have no ends
    with ends a, b:  L = |b − a|;  s = (H − a)·(b − a) / L
      s < 0 and −s > tol.decide       → extension = {a: a, b: H, length: |H − a|}
      s > L and s − L > tol.decide    → extension = {a: b, b: H, length: |H − b|}
      otherwise, or without ends     → extension "branch_absent"

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `zero_length` | `|b − a|` of a side segment (carrier) | `tol.decide` |
| `zero_length` | `h` | `tol.decide` |
| `outside_part` | `s` and `s − L` (with ends) | `tol.decide` |

## Checks

- `perpendicular`: `|(V − H)·d|`
- `on_carrier`: the distance from `H` to the carrier of `side`
