# `vector.by_points` — vector from a to b

Registry 1.2 · group `vector` · orientation `a_to_b` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point` |
| outputs | `vector: vector` |
| undefined | `upstream` |
| checks | `ends` |

## Value

    vector = {a: [ax, ay], b: [bx, by], length: hypot(bx − ax, by − ay)}

A zero vector (`a = b`) is defined: `length = 0`; the renderer draws no
arrow for it.

## Degeneracy decisions

None.

## Checks

- `ends`: the largest of `hypot(vector.a − a)`, `hypot(vector.b − b)` and
  `| length − hypot(bx − ax, by − ay) |`
