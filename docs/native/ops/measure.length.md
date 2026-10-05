# `measure.length` — length of a segment, vector, polyline or arc

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `of: measurable` |
| outputs | `number: number` |
| undefined | `upstream` |
| checks | none |

A measure reads the value of its argument: it has no degeneracies of
its own and is undefined only `upstream`.

## Value

    segment, vector, polyline: value = of.length
    arc:                       value = r·(a1 − a0)
    number = {value, unit: "length"}

## Degeneracy decisions

None.

## Checks

None.
