# `measure.circumference` — length of a circle

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `circle: circle` |
| outputs | `number: number` |
| undefined | `upstream` |
| checks | none |

A measure reads the value of its argument: it has no degeneracies of
its own and is undefined only `upstream`.

## Value

    number = {value: 2π·r, unit: "length"}

## Degeneracy decisions

None.

## Checks

None.
