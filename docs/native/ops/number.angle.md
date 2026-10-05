# `number.angle` — angle parameter

Registry 1.4 · group `number` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | none |
| params | `min`, `max`, `step` |
| free input | `angle` |
| outputs | `number: number` |
| undefined | `invalid_parameter`, `upstream` |
| checks | none |

A number the author sets as an angle (a slider for a turn, the size of
`angle.by_size`): the free input `{"kind": "angle", "value": φ}` in radians,
`0` when absent (kernel.md §1). The bounds are radians too; the input does not
count in the case scale `S`.

## Value

    if min and max are given and min > max:   → "invalid_parameter"
    if step is given and step ≤ 0:            → "invalid_parameter"
    v = input value (0 when absent)
    if min is given and v < min: v = min
    if max is given and v > max: v = max
    number = {value: v, unit: "angle"}

## Degeneracy decisions

None.

## Checks

None.
