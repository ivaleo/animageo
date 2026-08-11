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
| `Point`, `Line`, `Segment`, `Ray`, `Circle`, `Arc`, `CircleSector`, `Angle`, `Polygon`, `Vector`, `Conic`, `Function`, `ImplicitCurve` | `Midpoint`, `Distance`, `Length`, `Radius`, `Center`, `Vertex`, `Focus`, `Intersect`, `AreCollinear`, `Perpendicular`, `Parallel`, `Tangent`, `Polar`, … (99 command factories in total, dispatching to 433 type-specialized signatures in `COMMAND_REGISTRY` — one per argument-type combination) |

An unknown name raises a `NameError` — a clean failure, never a
silent no-op.

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
- Forward references for lowercase names: `B = Rotate(R, x*deg, Q)`
  works even if `x` is not defined yet (it will be supplied later by
  `scene.addVar('x', 115)`)

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
