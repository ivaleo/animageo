# `measure.area` — area of a polygon, disc, sector, circle segment or region

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
    circlesegment: value = r·r·(s − sin s) / 2,  s = a1 − a0  (registry 1.7)
    region:  value = of.area  (registry 1.9; the sum over the rings, kernel.md §16)
    number = {value, unit: "area"}

## Degeneracy decisions

None.

## Checks

None.
