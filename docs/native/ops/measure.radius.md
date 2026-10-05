# `measure.radius` — radius of a circle, arc or sector

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `of: round` |
| outputs | `number: number` |
| undefined | `upstream` |
| checks | none |

A measure reads the value of its argument: it has no degeneracies of
its own and is undefined only `upstream`.

## Value

    number = {value: of.r, unit: "length"}

## Degeneracy decisions

None.

## Checks

None.
