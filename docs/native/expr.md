# Expressions — AST v1

`number.expression` (registry 1.4, 1.8.1a5) computes a number from other
numbers by a formula. The formula is a tree of JSON nodes in the operation
argument `{"kind": "expr", "ast": Expr}`. No text is parsed and nothing is
`eval`-ed: the library and the web kernel check the tree against the rules
below and walk it node by node. Code: `animageo/native/expr/`
(`validate.py`, `evaluate.py`, `printer.py`); the operation page is
[ops/number.expression.md](ops/number.expression.md).

AST v1 is a **strict subset** of AST v2 of the expression language planned
for registry 1.6: every v1 tree is a v2 tree with the same value, so a v1
document is read by v2 code without migration. v2 adds nodes (`var`, `if`,
comparisons), functions and constants; v1 refuses them as `formula`.

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
