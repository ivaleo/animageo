# `number.expression` — value of an expression

Registry 1.4 · group `number` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `expr: expr`, `refs: number[]` (min 0) |
| outputs | `number: number` |
| undefined | `out_of_domain`, `non_finite`, `upstream` |
| checks | none |

A number computed from other numbers by a formula: the argument
`{"kind": "expr", "ast": Expr}` holds a tree of AST v1 (whitelist, limits,
order of evaluation, errors — [expr.md](../expr.md)); `{"ref": k}` reads the
value of item `k` (from 0) of the list input `refs` (numbers of any unit:
an angle in radians, a length in units). The result is `unit: "scalar"`.
A tree the rules refuse is the issue `formula` of `validate` (a JSON pointer
to the node) and the state `error/formula` of its element; nothing is
parsed from text and nothing is `eval`-ed.

## Value

    if problems(ast, len(refs)):   → error "formula"
    v = evaluate(ast, [r.value for r in refs])
        (post-order, left to right; the first node without a finite value
         gives "out_of_domain" or "non_finite", expr.md §3)
    number = {value: v + 0, unit: "scalar"}

## Degeneracy decisions

None.

## Checks

None.
