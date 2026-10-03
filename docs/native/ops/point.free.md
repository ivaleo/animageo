# `point.free` — free point

Registry 1.0 · group `point` · see [kernel.md](../kernel.md) for states, tolerances and fixtures.

| | |
|---|---|
| inputs | — |
| outputs | `point: point` |
| free | `{kind: "point"}` — the value comes from `inputs[elementId]` |
| undefined | — |
| checks | — |

## Value

The element bound to slot `point` reads `inputs[elementId] = {"kind": "point",
"value": [x, y]}` (case inputs override the document's):

    point = {x, y}

The numbers are taken as doubles (`1` and `1.0` are the same value).

## States

- No valid input value (missing, not `kind: "point"`, not two finite numbers)
  → `error/schema`.
- The free points of a case define the `D` term of the scene scale
  (kernel §5.1).
