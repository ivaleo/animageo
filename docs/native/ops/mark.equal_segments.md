# `mark.equal_segments` — equal-segment ticks

Registry 1.3 · group `mark` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `segments: segment` (list, at least 2) |
| params | `count: number` (unit `count`, optional, default `1`) |
| outputs | `mark: mark` |
| undefined | `invalid_parameter`, `upstream` |
| checks | `equal` |

A mark that the segments are equal: each segment gets `count` ticks across
its middle. The value is `{kind: "equal_segments", count}`; the geometry
of the mark is that of its arguments, so a renderer draws the ticks on the
segments (kernel.md §9.3, `tick_count`).

## Param

`count` is `1`, `2` or `3`; any other value (including a fraction) gives
`invalid_parameter`.

## Value

    if count ∉ {1, 2, 3}:   → undefined "invalid_parameter"
    mark = {kind: "equal_segments", count}

Whether the segments really are equal is not part of the value: the `equal`
check reports it. A `failed` check is a warning; the mark stays defined, so
a drawing that has stopped matching the claim is visible as such.

## Appearance (1.11.0rc13)

`appearance[markId].overrides.stroke: "#RRGGBB"` colours only the ticks;
`tick_count: 0|1|2|3` sets their drawn count (`0` hides them). Omitting the
keys restores the target's stroke / semantic `count`. The equality value
and checks are unchanged. Target count and size overrides win; the first
visible, defined mark in ID order owns the colour. See
[appearance priorities and diagnostics](../kernel.md#93-appearance).

## Degeneracy decisions

None.

## Checks

- `equal`: `max |L_i − L_1|` over the segments (`L` is the segment
  `length`)
