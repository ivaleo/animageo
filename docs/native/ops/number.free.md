# `number.free` — free number

Registry 1.2 · group `number` · free kind `number` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | none (the value is the input `{"kind": "number", "value": v}`) |
| params | `min: number`, `max: number`, `step: number` (all optional, no default) |
| outputs | `number: number` |
| undefined | `invalid_parameter` |
| checks | none |

A number the user sets (a slider, a typed radius). Its input does not count
in the case scale `S`.

## Value

    if min and max are given and min > max:   → undefined "invalid_parameter"
    if step is given and step ≤ 0:            → undefined "invalid_parameter"
    v = input value
    if min is given and v < min: v = min
    if max is given and v > max: v = max
    number = {value: v, unit: "scalar"}

`step` is for the interface only: the value is not snapped to it. A missing
input is `error/schema` (kernel.md §5.2).

## Degeneracy decisions

None.

## Checks

None.
