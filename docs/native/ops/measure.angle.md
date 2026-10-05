# `measure.angle` — size of an angle

Registry 1.4 · group `measure` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `angle: angle` |
| outputs | `number: number` |
| undefined | `upstream` |
| checks | none |

A measure reads the value of its argument: it has no degeneracies of
its own and is undefined only `upstream`. The size runs counterclockwise from the first side, `[0, 2π)`.

## Value

    number = {value: angle.size, unit: "angle"}

## Degeneracy decisions

None.

## Checks

None.
