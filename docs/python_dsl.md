# AnimaGeo Python DSL

A plain Python shell for building geometric constructions. Any valid
Python code works as DSL code, and factory calls (`Point`, `Midpoint`,
`Intersect`, …) both execute and register themselves in the
`Construction` dependency graph.

> **Status:** the exec-based engine is the only DSL engine.
>
> Entry points:
> * `scene.putCode(code)` / `scene.loadCode(filepath)`
> * `scene.loadGGB(filepath)` — GGB → exec (via `ggb_parser`)
> * `dsl.run(constr, code)` — direct call
> * `with dsl.scope(constr): ...` — ContextVar binding for file mode

## Table of contents
- [Quick start](#quick-start)
- [Syntax](#syntax)
- [Factories](#factories)
- [Formulas](#formulas)
- [Element naming](#element-naming)
- [Field access](#field-access)
- [Styles](#styles)
- [What is not allowed](#what-is-not-allowed)
- [What the exec engine supports](#what-the-exec-engine-supports)
- [Current limitations](#current-limitations)

## Quick start

With a standalone `Construction`:

```python
from animageo.geo.construction import Construction
from animageo.parsers import dsl

c = Construction()
dsl.run(c, """
    A = Point(0, 0)
    B = Point(4, 0)
    C = Point(0, 3)
    p, s1, s2, s3 = Polygon(A, B, C)
    M = Midpoint(A, B)
    style(M, stroke='#ff0000', size=10)
""")
```

With a manim scene (`AnimaGeoScene`):

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.putCode("""
            A = Point(0, 0)
            B = Point(3, 4)
            M = Midpoint(A, B)
        """)
        self.addAllGeometry(show=True)
```

Or import the factories directly in a .py file (with IDE hints):

```python
from animageo.parsers.dsl.namespace import Point, Midpoint, style
# Direct calls need an active Construction in the ContextVar —
# see dsl.registrar.set_current_construction, or use
# scene.putCode(code).
```

## Syntax

All of Python works:

```python
# loops
for i in range(5):
    p = Point(i, 0)            # creates p, p_2, p_3, p_4, p_5

# conditionals
for i in range(10):
    if i % 2 == 0:
        p = Point(i, 0)

# functions
def triangle(prefix, side):
    A = Point(0, 0, name=f"{prefix}_A")
    B = Point(side, 0, name=f"{prefix}_B")
    C = Point(side/2, side*0.866, name=f"{prefix}_C")
    return A, B, C

triangle("t1", 3)
triangle("t2", 5)

# list comprehensions work too
radii = [r for r in range(1, 6)]
circles = [Circle(Point(0, 0, name=f"O_{i}"), r) for i, r in enumerate(radii)]

# math — no `import` needed: ``math`` functions and constants
# (``pi``, ``sqrt``, …) are available globally in the DSL namespace
A = Point(sqrt(2), pi/2)
```

## Factories

Any CamelCase name that has a corresponding dispatchable function in
`animageo/geo/lib_commands.py` automatically becomes a factory.
Nothing needs to be registered by hand.

Key factories:

| Constructors | Commands |
|---|---|
| `Point`, `Line`, `Segment`, `Ray`, `Circle`, `Arc`, `CircleSector`, `Angle`, `Polygon`, `Vector`, `Conic`, `Function`, `ImplicitCurve` | `Midpoint`, `Distance`, `Length`, `Radius`, `Center`, `Vertex`, `Focus`, `Intersect`, `AreCollinear`, `PerpendicularLine`, `Tangent`, `Polar`, `Rotate`, `Dilate`, … (100 command factories in total, dispatching to 477 type-specialized signatures in `COMMAND_REGISTRY` — one per argument-type combination) |

An unknown name raises a `NameError` — a clean failure, never a
silent no-op.

## Formulas

`Function`, `Conic`, `ImplicitCurve` and `Line` take an equation as a
string. A line `name(var) = expr` is shorthand for `Function`:

```python
f = Function("y = x^2 + 1")
c = Conic("x^2 + y^2 = 4")
h = ImplicitCurve("x^3 + y^3 = 3x y")
l = Line("y = 2x + 1")
f(x) = x^2 + 1         # f = Function("y = x^2 + 1")
g(t) = 2t + 1          # a function of t
```

`Line` reads a string literal as an equation; `Line(A, B)`, `Line(s)` and
the other forms build the line as before. An equation that is not a line
(`Line("y = x^2")`) leaves the element undefined.

A formula may refer to objects of the construction and then follows
them: numbers and sliders, booleans, measures, angles, the
coordinates of points and vectors (`x(A)`, `y(A)`), and other
functions (`g(x)`):

```python
a = 2
A = Point(1, 3)
p(x) = a x^2                               # follows a
q = Function("y = x(A) + x")               # follows A
g(x) = x^2
r(x) = g(x - 2) + 1                        # follows g
k = Conic("(x - x(A))^2 + (y - y(A))^2 = 4")
m = Line("y = a x + 1")                    # follows a
b = AreCollinear(A, Point(0, 0), Point(2, 6))
s = Function("y = If(b, x, -x)")           # follows b
```

Such a formula is stored as a command with the names it refers to
appended — `Function("y = a x^2", a)` — and is re-read with their
current values on every rebuild. The objects must exist before the
formula is written; a name defined from itself
(`f = Function("y = f(x) + 1")` for an existing `f`,
`A = Midpoint(A, B)`) raises a dependency-cycle `ValueError`.

Formula syntax:

- `^` (or `**`) is a power. The `*` may be left out: `2x`, `k x`,
  `2(x + 1)`, `(x + 1)(x - 1)`, `x (x + 1)`.
- `x(A)` with no space before the bracket is A's x-coordinate, so
  `x(x + 1)` is not a product — write `x (x + 1)` or `x*(x + 1)`.
  `2x(A)` is twice A's x-coordinate.
- A number written before a bracket is a product: `k(x + 1)` is
  `k*(x + 1)`, unless the number is named like a math function —
  `gamma(x + 1)` is Γ(x + 1).
- A formula calls only math functions: `sin`, `cos`, `tan`, `cot`, `sec`,
  `csc`, `asin`, `acos`, `atan`, `sinh`, `cosh`, `tanh`, `exp`, `log`, `ln`,
  `sqrt`, `cbrt`, `root`, `abs`, `sign`, `floor`, `ceiling`, `round`,
  `frac`, `min`, `max`, `gamma`, `erf`, … — functions and implicit curves
  also take GeoGebra's spellings (`arcsin`, `sgn`, `ceil`, `lg`, `ld`) and
  `If(cond, a, b)`. Any other name a formula calls is an object of the
  construction. `round(x)` rounds half up, as in GeoGebra.
- `pi` and `π` are π, `ℯ` is Euler's number. `e` is Euler's number too in
  functions and implicit curves; in a conic or line equation it is an
  ordinary name — write `ℯ` or `exp(1)` there. `2π`, `πx`, `2ℯ` are
  products, like `2x`.
- Typographic characters are read as well: the minus sign `−`, `·`, `⋅`
  and `×` for multiplication, `÷` for division.
- A function that calls another one with a restricted domain is
  undefined wherever that one is.
- A conic or line equation has to be a polynomial as written:
  `(x^2 + x)/x = y` is not a conic.
- Formula text is limited to 4000 characters, and a formula that asks
  for a huge exact computation (`7^(9^9)`, `(10^7)!`) is refused.

A formula that cannot be read, or that names something the
construction does not have, leaves its element undefined and logs a
warning.

## Element naming

### From the variable on the left

```python
A = Point(0, 0)        # element registered as "A"
```

### In a loop — automatic uniquification

```python
for i in range(3):
    p = Point(i, 0)    # elements: p, p_2, p_3
```

### In a function — uniquification too (a `def` body is a loop scope)

```python
def make():
    A = Point(0, 0)
    return A

make()    # element: A
make()    # element: A_2
```

### Explicit name via `name=`

```python
def triangle(prefix):
    A = Point(0, 0, name=f"{prefix}_A")   # element: <prefix>_A
    B = Point(1, 0, name=f"{prefix}_B")
    return A, B
```

If `name=` is given and the name is already taken, a `ValueError` is
raised (no silent collision). The Python variable `A` is still bound
to the proxy.

### Tuple unpacking for commands with multiple outputs

```python
a, b = Intersect(c, L)                    # two intersection points
p, s1, s2, s3 = Polygon(A, B, C)          # polygon + three sides
```

The transformer injects `_outputs=N` into the call so the factory
allocates the right number of names.

If you need one specific point out of several intersections, use a
1-based index: `p = Intersect(c, L, index=1)`, or positionally,
`p = Intersect(c, L, 1)`.

Intersection order is part of the public contract. The first element
of a tuple unpack corresponds to `Intersect(..., index=1)`, the second
to `Intersect(..., index=2)`, and so on. For circles a GeoGebra-like
heuristic applies: if the circle was constructed through already-known
points, intersection points coinciding with them come first, in the
order of the circle's inputs; then the second input object's points
are considered, and the remaining intersections keep the internal
deterministic order. This order must stay identical across `.ggb`
import, the Python DSL, and the export/JSXGraph paths.

## Field access

Through the proxy that a factory returns:

```python
A = Point(3, 4)
print(A.x, A.y)           # 3.0, 4.0
print(A.coords)           # [3., 4.]

circ = Circle(Point(0, 0), 5)
print(circ.center)        # [0., 0.]
print(circ.radius)        # 5

s = Segment(Point(0, 0), Point(3, 4))
print(s.start, s.end, s.length)
```

Full list — `docs/field_names.md`.

Reads are live — after any `dsl.run` the fields reflect the current
state.

## Styles

`elem.style` is a `StyleProxy` (a `dict` subclass). Both APIs work at
the same time.

### Attribute-style (new)

```python
A = Point(3, 4)
A.style.stroke = "#ff0000"
A.style.size_px = 12
A.style.label_visible = True
```

### Dict-style (legacy — nothing broke)

```python
A.style["stroke"] = "#ff0000"
A.style.get("stroke", "black")
"stroke" in A.style
for k, v in A.style.items(): ...
json.dumps(A.style)           # still works
```

### Batch helpers

```python
style(A, B, C, stroke="#f00", size=10)
hide(A, B)
show(C)
```

A missing attribute returns `None` (not `AttributeError`), mirroring
CSS semantics: `if A.style.stroke:` — "is this style set?".

## What is not allowed

`DSLSyntaxError` at transform time, with line/col:

- `global x` / `nonlocal x`
- `A += expr` (augmented assignment)
- `(A := expr)` (walrus)
- `A: int = 5` (annotated assignment with a value)
- `A = B = expr` (chained assignment)
- Names with a leading underscore on the LHS (reserved for phantoms)

Silently dropped at transform time:

- `import module` / `from module import name` — kept in the source
  purely for IDE static analysis; the name is never bound at runtime

`NameError` at runtime:
- `open`, `eval`, `exec`, `__import__`, `compile` — not in the sandbox

## What the exec engine supports

- `for`, `if`, `while`, `def`, comprehensions, lambda — as in Python
- `**kwargs` in factories (`Point(3, 4, name='A')`)
- Unknown CamelCase command → `NameError` (clear message)
- Reassignment in the same scope updates the element; in a loop/`def`
  it auto-uniquifies to `name_2, name_3, …`
- Field access through proxies (`A.x`, `A.y`, `circ.center`, `seg.length`)
- Styles as attributes: `A.style.stroke = '#f00'`
- f-strings, tuple unpacking (`a, b = Intersect(c, l)`), arithmetic on
  proxies (`A - B` → a `Sub` command)
- Function notation `f(x) = x^2 + 1`, `g(t) = 2t + 1` (see
  [Formulas](#formulas))
- Forward references for lowercase names: `B = Rotate(R, x*deg, Q)`
  works even if `x` is not defined yet (it will be supplied later by
  `scene.addVar('x', 115)`). Formula strings are the exception: the
  names in them must exist when the formula is written
- A name defined from itself (`A = Midpoint(A, B)`) raises a
  dependency-cycle `ValueError` instead of hanging

## Current limitations

- The `.pyi` stubs declare 86 factory signatures (51 detailed typed
  signatures + 35 generic `*args: Any`); element constructors
  (`Point`, `Line`, …) are typed separately in `proxy.pyi`. For rarely
  used commands the IDE may show `Any` instead of a precise type.
  Extend them in `namespace.pyi` (runnable validator:
  `python3 -m animageo.parsers.dsl._regen_stubs`).
- Sandbox: `open`, `eval`, `exec`, `__import__`, `compile` are blocked
  — `NameError` at runtime. A top-level `import` is silently dropped
  (leaving room for IDE stubs, but the name is not bound at runtime).
