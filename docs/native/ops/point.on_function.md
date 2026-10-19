# `point.on_function` — a point on a graph by its x

Registry 1.6 · group `point` · status `beta` · free kind `pathParameter` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `function: function` |
| outputs | `point: point` |
| free input | `{"kind": "pathParameter", "value": x}` (required) |
| undefined | `out_of_domain`, `upstream` |
| checks | `on_graph` |

## Value

    x = input value, clamped to the domain [min, max] where it is given
    y = f(x);  no value  → undefined "out_of_domain"
    point = (x, y)

Dragging sets the input to the x of the pointer (no projection onto the
curve); the sampler of general position draws `x` around its value (unit 1).
The point is not a locus mover (`locus.of_point` refuses it as
`unsupported_signature`). The renderer holds `x` as the `tparam` of the
classic element, so a timeline of the input animates it as a point on a path.

## Checks

`on_graph` — `|y − f(x)|`.
