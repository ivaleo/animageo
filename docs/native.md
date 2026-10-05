# Native kernel (`animageo.native`)

`animageo.native` is the second way into animageo: a construction is a JSON
document (`animageo-construction/v1`) of operations and elements with stable
IDs, and the library evaluates, checks, edits, describes and renders it. The
classic API (`AnimaGeoScene`, the Python DSL, `loadGGB`) stays as it is; the
native kernel reads a `.ggb` or a classic DSL scene into a document when you
need one.

| | Classic API | Native kernel |
|---|---|---|
| Construction | `Construction` in memory, objects by name | JSON document, objects by ID |
| Built from | a `.ggb`, the Python DSL | a document, «Команды», a `.ggb` or a DSL scene (import) |
| Needs manim | yes | only to render |
| Contract | the API reference | a JSON schema, a frozen operation registry, parity fixtures |

The web editor of animageo.ru keeps its drawings as native documents; a
browser kernel in TypeScript repeats the evaluation, and the fixtures this
library generates are the reference for it.

## Quick start

```python
from animageo import native

result = native.parse_commands(
    "A = (0, 0)\nB = (4, 0)\nC = (1, 3)\n"
    "t, c, a, b = Многоугольник(A, B, C)\nM = Середина(A, B)")
doc = result.document                     # result.issues lists the problems of the text

ev = native.evaluate(doc)                 # values, states and reasons by element ID
native.describe(doc)                      # ['1. Строим треугольник ABC.', '2. Отмечаем середину M отрезка AB.']
print(native.print_commands(doc).text)    # back to «Команды»
native.render(doc, fmt='svg', out='triangle.svg')    # manim and LaTeX needed here
```

A `.ggb` becomes a document with a report of what was translated:

```python
import uuid
from animageo import native

namespace = str(uuid.uuid5(uuid.NAMESPACE_URL, 'https://example.org/works/42'))
doc, report = native.from_ggb('drawing.ggb', id_namespace=namespace)
# doc is None when nothing could be imported; report is import_report.v1
```

The same from the command line, without manim:

```bash
python -m animageo.native from-ggb drawing.ggb -o doc.json --report report.json
python -m animageo.native validate doc.json
python -m animageo.native evaluate doc.json
python -m animageo.native describe doc.json
```

## What to read

- [API reference](native/api.md) — every public name with its signature.
- [Kernel contract](native/kernel.md) — the document, the registry, evaluation,
  edits, rendering.
- [Checks](native/checks.md), [conditions](native/conditions.md),
  [steps](native/steps.md), [time](native/timeline.md).
- [«Команды»](native/commands.md) — the text form of a document;
  [expressions](native/expr.md) of `number.expression`.
- [Import](native/import.md) — `.ggb` and classic DSL scenes, `import_report.v1`.
- [Deprecations](native/deprecations.md) — what is deprecated and when it goes.

## Stability

- The names and signatures of [the API reference](native/api.md) are a
  snapshot (`tests/snapshots/public_api.json`); they change only with a
  CHANGELOG entry, and nothing is removed before 2.0 (after a deprecation
  warning, see [deprecations](native/deprecations.md)).
- The operation registry `1.5` is the 1.0 contract: an operation of it keeps
  its signature forever, and any other change needs a new registry version
  ([kernel.md §4](native/kernel.md)).
- `native.has(feature)` tells whether the installed library has a feature,
  so a consumer can check before it relies on one.

## Safety

The native kernel runs no code it is given: no `exec`/`eval`, no imports by
name, no processes (a lint over `animageo/native/**` checks it), and the
importers survive random and hostile input (fuzz tests run in CI). LaTeX of
labels compiles with `-no-shell-escape`, so a `\write18` in a label runs
nothing; restricting what TeX may read (`openin_any=p`) is up to the caller's
environment. The classic DSL is Python: run code you did not write in a
sandbox.

## `import animageo` is light

Since 1.11.0rc1 `import animageo` and `import animageo.native` load neither
manim nor the classic modules; the classic API (`from animageo import
AnimaGeoScene`, `from animageo import *`) loads on first use and gives the
same names as before.
