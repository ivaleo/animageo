# `segment.by_points` — segment between two points

Registry 1.0 · group `line` · orientation `a_to_b` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| outputs | `segment: segment` |
| undefined | `upstream` |
| checks | `ends` |

## Value

    segment = {a: [ax, ay], b: [bx, by], length: hypot(bx − ax, by − ay)}

The ends keep the definition order. A zero-length segment (`a = b`) is
**defined**; operations that need its direction decide `zero_length`
themselves (see `intersect.line_line`).

## Degeneracy decisions

None.

## Checks

- `ends`: `max(hypot(segment.a[0] − ax, segment.a[1] − ay), hypot(segment.b[0] − bx, segment.b[1] − by))`
