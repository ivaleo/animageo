# `point.divide` — point dividing a segment in a ratio

Registry 1.4 · group `point` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `a: point`, `b: point`, `m: number`, `n: number` |
| outputs | `point: point` |
| undefined | `invalid_parameter`, `upstream` |
| checks | `ratio` |

The point `P` with `AP : PB = m : n` on the segment `ab` (internal
division). `m` and `n` are numbers (literals or `number` elements); the
share `k = m / (m + n)` is a derived quantity, not an input.

## Value

    m = m.value,  n = n.value,  s = m + n
    if m < −tol.scalar or n < −tol.scalar or s ≤ tol.scalar:   → "invalid_parameter"
    point = ((n·ax + m·bx) / s, (n·ay + m·by) / s)

## Degeneracy decisions

| decision | value `m` | tolerance |
|---|---|---|
| `invalid_parameter` | `m` | `tol.scalar` |
| `invalid_parameter` | `n` | `tol.scalar` |
| `invalid_parameter` | `s` | `tol.scalar` |

## Checks

- `ratio`: `|n·(P − a) − m·(b − P)| / s`
