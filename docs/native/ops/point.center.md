# `point.center` — centre of a circle, arc or sector

Registry 1.4 · group `point` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `of: round` |
| outputs | `center: point` |
| undefined | `upstream` |
| checks | `matches` |

The centre `c` of a circle, an arc or a sector (family `round`).

## Value

    center = {x: c[0], y: c[1]}

## Checks

- `matches`: `|center − c|`
