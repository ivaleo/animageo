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

## Degeneracy decisions

None.

## Checks

- `equal`: `max |m(size_i) − m(size_1)| · S` over the angles, with the
  convex measure `m(size) = size` when `size ≤ π`, else `2π − size`: an angle
  and its reflex complement count as equal, as on a drawing
