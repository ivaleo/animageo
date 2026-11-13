# `vector.expression` — vector by a formula

Registry 1.10 · group `vector` · status `beta` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `expr: expr` (`result: "vec"`), `refs: operand[]` (min 0) |
| outputs | `vector: vector` |
| undefined | `out_of_domain`, `non_finite`, `upstream` |
| checks | none |

A vector computed by a typed formula ([expr.md](../expr.md) §6), with the
operands, nodes and errors of [`point.expression`](point.expression.md):
`B − A`, `0.5·u`, `−u`, `(1, f(1))`, `u + v`. The formula gives the
components; the vector starts at the origin, as a GeoGebra vector without a
start point. A vector drawn elsewhere is a `transform.translate` of it, a
turned one `transform.rotate`; its length is `measure.length`.

## Value

    if problems(ast, len(refs), operands=[r.type for r in refs], result="vec"):  → error "formula"
    (x, y) = evaluate_typed(ast, refs, "vec")
    vector = {a: [0, 0], b: [x + 0, y + 0], length: hypot(x, y)}

A zero vector is defined (`length = 0`); the renderer draws no arrow for it.

## Degeneracy decisions

None.

## Checks

None.
