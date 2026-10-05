# `measure.area` — area of a polygon, disc or sector

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `of: bounded` |
| outputs | `number: number` |
| undefined | `upstream` |
| checks | none |

A measure reads the value of its argument: it has no degeneracies of
its own and is undefined only `upstream`. The area of a polygon is unsigned (`polygon.area`).

## Value

    polygon: value = of.area
    circle:  value = π·r·r
    sector:  value = r·r·(a1 − a0) / 2
    number = {value, unit: "area"}

## Degeneracy decisions

None.

## Checks

None.
