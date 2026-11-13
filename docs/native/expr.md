# Expressions — AST v1

`number.expression` (registry 1.4, 1.8.1a5) computes a number from other
numbers by a formula. The formula is a tree of JSON nodes in the operation
argument `{"kind": "expr", "ast": Expr}`. No text is parsed and nothing is
`eval`-ed: the library and the web kernel check the tree against the rules
below and walk it node by node. Code: `animageo/native/expr/`
(`validate.py`, `evaluate.py`, `printer.py`); the operation page is
[ops/number.expression.md](ops/number.expression.md).

AST v1 is a **strict subset** of the trees of a function (registry 1.6,
§5): every v1 tree has the same value there, so a v1 document is read
without migration. The nodes of §5 (`var`, `if`, comparisons) are allowed
only in an `expr` slot whose record lists `vars` (`function.expr`); every
other slot refuses them as `formula`. In the same way the nodes of typed
expressions (registry 1.10, §6: pairs, calls of functions, `x()`, `y()`)
stand only in a slot whose record has `result`.

## 1. Nodes

```text
Expr := {"num": v}                                   a finite number
      | {"const": "pi"}                              π
      | {"ref": k}                                   item k (from 0) of the list input refs
      | {"op": "+" | "-" | "*" | "/" | "^", "args": [Expr, Expr]}
      | {"op": "neg", "args": [Expr]}                unary minus
      | {"fn": name, "args": [Expr, …]}
```

| function | arity | domain |
|---|---|---|
| `sqrt` | 1 | `x ≥ 0` |
| `abs` | 1 | all |
| `sin`, `cos`, `tan`, `atan` | 1 | all (radians) |
| `asin`, `acos` | 1 | `−1 ≤ x ≤ 1` |
| `exp` | 1 | all (an overflow is `non_finite`) |
| `ln`, `lg` (base 10) | 1 | `x > 0` |
| `min`, `max` | 2 | all |

- A node has exactly one of `num`, `const`, `ref`, `op`, `fn`, plus `args`
  for `op` and `fn`, and no other key.
- `ref` is an integer `k ≥ 0` below the number of items of `refs`; an
  integral float (`1.0`) counts as an integer, since JSON does not tell
  them apart. The items of `refs` are `number` elements of any unit (an
  angle in radians).
- The result is a `number` with `unit: "scalar"`.

## 2. Limits and the issue `formula`

| limit | value (`_numeric.json → expr`) |
|---|---|
| depth (the root is at depth 1) | 32 |
| nodes | 256 |
| `abs(n)` of an integer literal exponent | 64 |

A tree that breaks a rule of §1 or a limit is the issue `formula` of
`validate` (severity `error`), with `path` = the pointer of the argument +
`/ast` + the JSON pointer of the node (`/operations/op_e/args/expr/ast/args/1`).
`problems(ast, ref_count)` lists them in pre-order, left to right; the walk
does not recurse, does not descend past depth 32 and stops after 256 nodes.
The element of such an operation evaluates to `error/formula`. A non-`expr`
argument in the `expr` slot, or an `expr` argument in another slot, is
`type_mismatch`.

## 3. Evaluation

Post-order, left to right; each node is one IEEE-754 double operation.
`+` and `*` are not reordered and nothing is folded.

| node | value | undefined |
|---|---|---|
| `num`, `const`, `ref` | the number, `π` (`Math.PI`), the value of `refs[k]` | — |
| `neg` | `−a` | — |
| `a + b`, `a − b`, `a · b` | IEEE | — |
| `a / b` | IEEE | `b = 0` → `out_of_domain` |
| `a ^ n`, `n` an integral literal `{"num": n}` | binary powering: `r = 1; b = a; m = abs(n); while m: if m & 1: r = r·b; b = b·b; m >>= 1`; `n < 0` → `1 / r` | `n < 0` and `r = 0` → `non_finite` |
| `a ^ b`, any other exponent | `pow(a, b)` | `a = 0`, `b < 0` → `non_finite`; `a < 0`, `b` not integral → `out_of_domain` |
| `sqrt(a)` | `sqrt` | `a < 0` → `out_of_domain` |
| `ln(a)`, `lg(a)` | `log`, `log10` | `a ≤ 0` → `out_of_domain` |
| `asin(a)`, `acos(a)` | | `a < −1` or `a > 1` → `out_of_domain` |
| `min(a, b)` | `b < a ? b : a` (not `Math.min`: the order decides `−0`) | — |
| `max(a, b)` | `b > a ? b : a` | — |
| other functions | the libm function | — |

After every node: a value that is not finite (an overflow) → `non_finite`.
The first node without a finite value decides the reason: the domain is
checked before the operation, finiteness after it. The final value `−0`
comes out as `0`. The arithmetic rows and `sqrt` are bit-exact in both
kernels; the libm functions and `pow` may differ in the last bits and are
compared within the parity tolerance.

## 4. Text

`to_text(ast, names)` prints a tree for «Команды» and messages: precedence
from low to high `+ −`, `· /`, unary minus, `^` (right-associative), atoms;
a right operand of the same level keeps its parentheses; `{"ref": k}`
prints the name of `refs[k]`. The grammar of «Команды» 1.8.1 has no
expressions yet: the printer writes the line (`e = sqrt(a) + b^3`) with the
warning `unprintable_operation`, the parser refuses it as `forbidden`, and
an edit of the text keeps the operation as it was (commands.md §8).

## 5. Functions of `x` (registry 1.6)

The slot `expr` of [function.expr](ops/function.expr.md) has `"vars": ["x"]`
in its record. Its tree takes the nodes of §1 and:

```text
Expr += {"var": "x"}                                  the variable
      | {"if": [Cond, Expr]}                          Expr where Cond holds, no value elsewhere
      | {"if": [Cond, Expr, Expr]}                    the second Expr where Cond fails
Cond := {"cmp": "<" | "<=" | ">" | ">=", "args": [Expr, Expr]}
      | {"and": [Cond, Cond]} | {"or": [Cond, Cond]} | {"not": [Cond]}
```

- A condition stands only in the first place of `if` and inside `and`,
  `or`, `not`; a value never stands there (`formula` at the pointer of the
  node, `/if/0`, `/and/1`…). `var` names a variable of the slot.
- The limits of §2 count every node, conditions included.
- Evaluation is §3; `if` evaluates its condition and then only the chosen
  branch; `and`/`or` stop at the first operand that decides; a comparison
  is the IEEE comparison of two values (any undefined operand makes the
  whole value undefined). `if` without the third item where the condition
  fails is `out_of_domain`: the graph has no point there.
- `compile_function(ast, refs)` (`expr/function.py`) turns the tree into
  `f(x)` once (closures), with the semantics of §3 node by node.
- `to_text` prints `x`, `If(x < 0, −x, x)`, `(a) && (b)`, `(a) || (b)`, `!(a)`.

## 6. Typed expressions (registry 1.10)

An `expr` slot whose record has `"result": "num"` or `"result": "vec"` is
**typed** ([point.expression](ops/point.expression.md),
[vector.expression](ops/vector.expression.md): `"vec"`). Its values are
numbers (`num`) and pairs (`vec`), and its `refs` are of the family
`operand` (`number`, `point`, `vector`, `function`). Slots without
`result` (the records of 1.4–1.9) refuse the nodes below as `formula`, as
before (`x` is an unknown function, `pair` and `call` unknown nodes);
`result` and `vars` never stand together.

```text
Expr (typed slot) += {"pair": [Expr, Expr]}             a vec from two nums
                   | {"call": k, "args": [Expr]}        the value of the function refs[k] at a num
                   | {"fn": "x" | "y", "args": [Expr]}  a component of a vec
```

Node shapes follow §1 (one kind key, no other key; `pair` exactly 2
values, `call` exactly 1 argument and `k` a valid index of `refs`); no
conditions; the limits of §2 count `pair` and `call` as nodes.

| item of `refs` | type in the tree | value |
|---|---|---|
| `number` (any unit; an angle in radians) | `num` | its value |
| `point` | `vec` | `(x, y)` |
| `vector` | `vec` | its components `(b.x − a.x, b.y − a.y)`, not its end |
| `function` | `fn` | only as the target of `call`; a bare `{"ref": k}` is a type error |

| node | types → result | value |
|---|---|---|
| `a ± b` | `vec ± vec → vec`, `num ± num → num` | `(a.x ± b.x, a.y ± b.y)` |
| `k · v`, `v · k` | `num·vec`, `vec·num → vec` | `(k·v.x, k·v.y)` |
| `v / k` | `vec / num → vec` | `(v.x / k, v.y / k)`; `k = 0` → `out_of_domain` |
| `u · v` | `vec·vec → num` | `u.x·v.x + u.y·v.y` (two products, then the sum) |
| `neg v` | `vec → vec` | `(−v.x, −v.y)` |
| `x(v)`, `y(v)` | `vec → num` | the component |
| `abs(v)` | `vec → num` | `hypot(v.x, v.y)` (as `length` of `vector.by_points`) |
| `pair(a, b)` | `num, num → vec` | `(a, b)` |
| `call(f, t)` | `fn, num → num` | `f(t)` (`kernel/function.evaluator`); no value (outside the domain, a branch of `If` without one, a pole) → `out_of_domain` |
| every other node of §1 | `num` only | §3 |

A degree is a number: `α + 30°` is written `α + 30·(pi/180)`.

**Type errors** — `vec + num` (`A + 1`), `num / vec`, `vec / vec`,
`vec ^ n`, `n ^ vec`, `sin(vec)` and any other function of §1 but `abs`
with a `vec`, `x(num)`, a `pair` with a `vec`, a `call` of an item that is
not a function, a `call` with a `vec`, a bare function — are static: the
issue `formula` with the pointer of the node, the state `error/formula`.
A root of the other type than `result` is reported at the pointer `""`.

`problems(ast, ref_count, vars=(), operands=None, result=None)` runs the
structure of §2 first; when it finds nothing and `operands` (the element
types of `refs`) is given, a second pass types the tree bottom-up over the
pre-order list (no recursion) and reports the first mistake of each node,
in pre-order. A node whose child has no type gets none and no problem of
its own, so a mistake is reported once: in `(A + 1)·2` only the sum. When
an item of `refs` does not fit `operand` (`type_mismatch`) or dangles
(`dangling_ref`), the tree is checked for its structure only.

**Evaluation** — `evaluate_typed(ast, operands, result)`: post-order, left
to right, and inside a pair `x` before `y`; the domain is checked before an
operation and finiteness after it, for each component (an overflow of
either component is `non_finite`). The final `−0` comes out as `0` in each
component. The arithmetic, `sqrt`, the integer power, `pair`, `x`, `y` and
the dot product are bit-exact in both kernels; `hypot`, the libm functions
and `call` (a function body with libm) are compared within the parity
tolerance.

**Text** — `to_text`: `pair` prints `(a, b)`, `call` `f(1)` (the name of
`refs[k]`), `x(P)`, `abs(u)`; `pair` and `call` are atoms, the precedence
is §4 (`-(1, 2)`, `2·(1, 2)`, `f(2)^2`, `t·A + (1 - t)·M`). «Команды» do
not print the formula of a point or a vector: `(2, 3)` would read back as a
free point. They print the operation with `unprintable_operation`, and an
edit keeps it.
