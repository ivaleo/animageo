# `segment.from_point_length` — segment of a given length from a point

Registry 1.4 · group `line` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `start: point`, `length: number` |
| free input | `angle` |
| outputs | `segment: segment`, `end: point` |
| orientation | `a_to_b` |
| undefined | `invalid_parameter`, `upstream` |
| checks | `length` |

A segment of length `length` from `start`. The operation is free: its input
`{kind: "angle", value: θ}` (radians, default 0 when absent) is the
direction, so dragging the end changes the input and not the length.

## Value

    θ = input.value (0 when absent),  ℓ = length.value
    if ℓ < −tol.decide:     → both slots "invalid_parameter";  ℓ < 0 → ℓ = 0
    end = start + ℓ·(cos θ, sin θ)
    segment = {a: start, b: end, length: ℓ}

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `invalid_parameter` | `ℓ` | `tol.decide` |

## Checks

- `length`: `| |end − start| − ℓ |` and `|segment.a − start|`
