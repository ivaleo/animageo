# `mark.parallel` — parallel-line chevrons

Registry 1.8 · `beta` · group `mark` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `lines: straight` (list, at least 2) |
| params | `count: number` (unit `count`, optional, default `1`) |
| outputs | `mark: mark` |
| undefined | `invalid_parameter`, `upstream` |
| checks | `parallel` |

A mark that the lines are parallel: each of them gets `count` chevrons in
its middle, all pointing the same way. Family `straight`: `line`,
`segment`, `ray`, `vector` (a side of a polygon is a segment, `side.i`).
The value is `{kind: "parallel", count}`; the geometry of the mark is that
of its arguments, so a renderer draws the chevrons on the lines
(kernel.md §9.3, `parallel_count`).

## Param

`count` is `1`, `2` or `3`; any other value (including a fraction) gives
`invalid_parameter`.

## Value

    if count ∉ {1, 2, 3}:   → undefined "invalid_parameter"
    mark = {kind: "parallel", count}

Whether the lines really are parallel is not part of the value: the
`parallel` check reports it. A `failed` check is a warning; the mark stays
defined, so a drawing that has stopped matching the claim is visible as
such.

## Direction of the chevrons

The direction of an item is `b − a` of a segment or a vector, `dir` of a
line or a ray. The reference is the first item whose direction has a
non-zero length; an item whose direction `d` has `d · d_ref < 0` gets
`parallel_direction = "backward"`, every other item `"forward"`
(`kernel/ops/mark.py → parallel_directions`). So the chevrons of all the
targets point the same way on the sheet, whatever the order of the points
that define each line. The directions are those of the evaluated values at
the drawn moment; they are not part of the mark value.

## Appearance

`appearance[markId].overrides.stroke: "#RRGGBB"` colours only the chevrons;
`parallel_count: 0|1|2|3` sets their drawn count (`0` hides them);
`parallel_direction: "backward"` turns the chevrons of every target
(relative to the reference above). `parallel_size_px` and
`parallel_shift_px` go to the targets as well. A target's own
`parallel_*` keys win. The chevrons are a decoration channel of their own,
separate from the ticks of an equality mark, so one segment can carry both
(kernel.md §9.3).

## Degeneracy decisions

None.

## Checks

- `parallel`: `max_i |u_1 × u_i| · S` over the unit directions `u_i` of the
  lines (`S` the scale of the document). A segment or a vector not longer
  than `tol.decide_length` has no direction: the error is `+∞`, the check
  is `inconclusive`.
