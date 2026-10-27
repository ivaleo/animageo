# `mark.equal_angles` — equal-angle arcs

Registry 1.3 · group `mark` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `angles: angle` (list, at least 2) |
| params | `count: number` (unit `count`, optional, default `1`) |
| outputs | `mark: mark` |
| undefined | `invalid_parameter`, `upstream` |
| checks | `equal` |

A mark that the angles are equal: each angle gets `count` arcs. The value
is `{kind: "equal_angles", count}`; the geometry of the mark is that of its
arguments (kernel.md §9.3, `tick_count` on the angles).

## Param

`count` is `1`, `2` or `3`; any other value gives `invalid_parameter`.

## Value

    if count ∉ {1, 2, 3}:   → undefined "invalid_parameter"
    mark = {kind: "equal_angles", count}

## Appearance (1.11.0rc13)

`appearance[markId].overrides.stroke: "#RRGGBB"` colours only the arcs;
`tick_count: 0|1|2|3` sets their drawn count (`0` hides them). Omitting the
keys restores the target's stroke / semantic `count`. With `tick_count` the
mark draws arcs even at 90 degrees; a colour alone keeps the square. The angle's fill and its sides'
styles, the equality value and checks are unchanged. Target count and size
overrides win; the first visible, defined mark in ID order owns the colour.
See [appearance priorities and diagnostics](../kernel.md#93-appearance).

## Degeneracy decisions

None.

## Checks

- `equal`: `max |m(size_i) − m(size_1)| · S` over the angles, with the
  convex measure `m(size) = size` when `size ≤ π`, else `2π − size`: an angle
  and its reflex complement count as equal, as on a drawing
