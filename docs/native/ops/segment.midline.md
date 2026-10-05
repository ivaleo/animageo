# `segment.midline` — segment joining the midpoints of two segments

Registry 1.4 · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `first: segment`, `second: segment` |
| outputs | `segment: segment`, `mid.1: point`, `mid.2: point` |
| orientation | `a_to_b` |
| undefined | `upstream` |
| checks | `midpoints` |

The segment joining the midpoints of two segments (a midline of a triangle
or a trapezoid when the segments are its sides) and the midpoints.

## Value

    mid.1 = (first.a + first.b) / 2,  mid.2 = (second.a + second.b) / 2
    segment = {a: mid.1, b: mid.2, length: |mid.2 − mid.1|}

## Checks

- `midpoints`: the largest distance to the midpoints
