# `point.expression` — point by a formula

Registry 1.10 · group `point` · status `beta` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `expr: expr` (`result: "vec"`), `refs: operand[]` (min 0) |
| outputs | `point: point` |
| undefined | `out_of_domain`, `non_finite`, `upstream` |
| checks | none |

A point computed by a typed formula ([expr.md](../expr.md) §6) over the
items of `refs` of the family `operand`: a number is its value (an angle in
radians), a point the pair `(x, y)`, a vector its components
`(b.x − a.x, b.y − a.y)`, a function is read only through a call `f(t)`.
The tree must give a pair: `A + u`, `t·A + (1 − t)·B`, `(c_x, 4)`,
`(2, f(2))`, `A + 2·(B − A)`. The slot record carries `result: "vec"`, so
the tree also takes `{"pair": [E, E]}`, `{"call": k, "args": [E]}` and
`x(V)`, `y(V)`, and is typed with the element types of `refs`.

An item of `refs` outside `operand` is `type_mismatch`, a dangling one
`dangling_ref` (the tree is then not typed). A tree the rules refuse — a
structure problem or a type mistake (`A + 1`, `sin(A)`, `u / v`, a formula
that gives a number) — is the issue `formula` of `validate` with the JSON
pointer of the node (`""` when the whole tree has the wrong type) and the
state `error/formula` of the point.

The point is not free: it follows its inputs. `appearance.<id>.drag.via`
drags it through free inputs upstream of it (kernel.md §8.1), as any
dependent point.

## Value

    if problems(ast, len(refs), operands=[r.type for r in refs], result="vec"):  → error "formula"
    (x, y) = evaluate_typed(ast, refs, "vec")
        (post-order, left to right, x before y; a domain check before the
         operation, finiteness after it, for each component; expr.md §6)
    point = {x: x + 0, y: y + 0}

Division by zero, a root of a negative number and a call of a function
outside its domain (or in a branch without a value) are `out_of_domain`; a
component that overflows is `non_finite`.

## Degeneracy decisions

None.

## Checks

None.
