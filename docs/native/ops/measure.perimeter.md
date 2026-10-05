# `measure.perimeter` — perimeter of a polygon, disc or sector

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `of: bounded` |
| outputs | `number: number` |
| undefined | `upstream` |
| checks | none |

A measure reads the value of its argument: it has no degeneracies of
its own and is undefined only `upstream`. A full sector (`a1 = a0 + 2π`) still counts both radii.

## Value

    polygon: value = Σ hypot(V[(i + 1) mod n] − V[i]),  i = 0 … n − 1 in order
    circle:  value = 2π·r
    sector:  value = r·(a1 − a0) + 2·r
    number = {value, unit: "length"}

## Degeneracy decisions

None.

## Checks

None.
