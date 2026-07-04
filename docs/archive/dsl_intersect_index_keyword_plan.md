# Plan: DSL `Intersect(index=...)` Consistency

## Goal

Make indexed intersections consistent across the public Python DSL and the
lower-level `lib_commands` dispatch layer.

At the moment, many lower-level intersection commands support an indexed form,
for example `intersect_lci(line, circle, index, ...)`, but the public DSL
factory accepts only generic positional args plus `name=` and `_outputs=`.
Therefore this fails in generated/user DSL:

```python
P = Intersect(line, circle, index=1)
```

while the lower-level command family already has index-aware dispatch variants.

## Why This Matters

- AI generation naturally emits `index=` because it is semantically clear.
- Users expect public DSL and library capabilities to be aligned.
- Current docs already mention indexed intersection examples, but the public
  callable surface is ambiguous.
- Render failures caused by `unexpected keyword argument 'index'` are avoidable
  with a small DSL namespace improvement.

## Desired Public Contract

Support all existing forms:

```python
P1, P2 = Intersect(line, circle)
P1 = Intersect(line, circle, 1)
P1 = Intersect(line, circle, index=1)
```

Also keep unique intersections simple:

```python
D = Intersect(line1, line2)
```

Do not require users to pass an index when the intersection is unique.

## Index Base Decision

Resolve and document the index base explicitly.

Current `lib_commands.res_by_index()` subtracts one from the supplied index:

```python
index = int(max(0, index - 1))
```

This means positive indexed command variants behave like 1-based indexing,
while some docs currently show examples such as:

```python
P1 = Intersect(line, circle, 0)
P2 = Intersect(line, circle, 1)
```

The implementation task must choose one public convention and make docs/tests
match it. Recommended: keep library behavior backward-compatible and document
the public indexed form as 1-based (`1`, `2`, ...), while preserving current
`0` behavior if it already maps to the first result.

## Implementation Sketch

1. Update `animageo/parsers/dsl/namespace.py`.
2. Let the generated factory accept selected semantic kwargs for known commands,
   at least `Intersect(index=...)`.
3. Convert `Intersect(a, b, index=n)` to positional args before creating
   `Command("Intersect", ...)`.
4. Preserve `name=` and `_outputs=` behavior.
5. Reject unsupported kwargs with clear errors.
6. Update `animageo/parsers/dsl/namespace.pyi` so type hints expose
   `index: Optional[int]`.
7. Update DSL docs/examples to use the chosen index base.

## Tests

Add tests that cover:

- `P1 = Intersect(line, circle, index=1)` runs through DSL without
  `TypeError`.
- The keyword form creates the same result as the equivalent positional indexed
  form.
- `P1, P2 = Intersect(line, circle)` still works.
- `D = Intersect(line1, line2)` still works without index.
- Unsupported kwargs such as `foo=1` still fail clearly.

## Acceptance Criteria

- Public DSL accepts `Intersect(..., index=n)`.
- Existing positional and tuple-unpack intersection DSL continues to work.
- Docs and stubs no longer imply a different contract than runtime behavior.
- AI-generated DSL using semantic `index=` no longer fails at namespace-call
  time.
