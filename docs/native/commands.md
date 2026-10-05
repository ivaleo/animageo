# «Команды» — the text form of a construction document (L2, L3)

`animageo/native/commands/` turns text in the «Команды» notation into an
`animageo-construction/v1` document and back. It is the reference for the web
app's browser parser: both read the same lexicon and pass the same fixtures
(§9). The notation is appendix Б of the constructions spec of the web app;
the library implements the subset of it described here and refuses the rest
with the error `forbidden`. Pure Python: nothing here imports manim or the
classic modules.

```python
from animageo import native

result = native.parse_commands("A = (0, 0)\nB = (4, 0)\nM = Середина(A, B)")
result.document          # NativeDocument
result.effects           # what changed (kernel.md §8 shape)
result.lines             # [{line, operationIds, elementIds}]
result.issues            # [CommandIssue]
native.print_commands(result.document).text   # the same three lines
native.parse_commands(edited_text, base=result.document)   # edit mode (§8)
```

## 1. API

```text
parse_commands(text, *, lexicon=None, base=None, id_factory=None, document_id=None) -> ParseResult
print_commands(doc, *, lexicon=None) -> PrintResult
ParseResult(document, effects, lines, issues, conditionRequests, queries)   # §12
PrintResult(text, lines, issues)
CommandIssue(code, line, column, message, severity, hint=None)    # .to_dict()
default_lexicon() -> dict           lexicon_problems(data) -> [str]
lexicon_hash(data) -> "sha256:…"    Lexicon(data)  # raises LexiconError(problems)
next_name(type, taken) -> str       polygon_side_names(vertices, taken) -> [str]
format_number(x) -> str             is_helper(doc_data, op_id) -> bool
time_ordered_id() -> str
apply_condition_requests(doc, requests, *, id_factory=None, marks=True) -> RequestsResult   # §12
printable_document(doc) -> dict    # §12
```

`parse_commands` and `print_commands` are also exported from
`animageo.native`; the rest lives in `animageo.native.commands`.

- `lexicon`: an `animageo-lexicon/v1` dict or a `Lexicon`. `None` means
  the copy shipped with the library (§4.4), which is meant for the command
  line and tests. The web app's lexicon is the source of truth.
- `base=None` builds a new document: its `documentId` is `document_id` or
  a random UUID, and its `operationRegistryVersion` is the current registry
  version. With `base`, the text edits that document (§8).
- `id_factory(kind)` returns new IDs. `kind` is `"operation"` or
  `"element"`; a factory without parameters is called bare. An ID must match
  `[A-Za-z0-9_-]{1,64}` (`ValueError` otherwise). IDs already in use are
  skipped, so a counter can be passed as is.
- **IDs must grow in creation order.** The printer orders lines that do
  not depend on each other by operation ID (§6.1), so the IDs decide where
  such lines print. A client that brings its own IDs (`id_factory`, or the
  operations of `base`) must make them time-ordered: UUID v7 or ULID, which
  sort as strings in creation order. With random IDs (`uuid4`) independent
  lines change places after a print, and a later line that refers to a line
  that moved below it gets `unknown_name`.
- The default factory is `time_ordered_id()`: UUIDs with the version 7
  layout (48-bit milliseconds, a 12-bit counter for IDs made in the same
  millisecond, random bits) that increase within the process.
- `lines` gives one entry per applied line, in text order:
  `{line, operationIds, elementIds}`. `operationIds` starts with the line's
  operation, followed by the hidden operations its arguments created (§3).
  `elementIds` are the outputs of the line's operation.
- A line with an error is skipped: `issues` gets the error, and the document
  is built from the other lines. `issues` also holds the warnings
  `ambiguous_name` (§3) and is sorted by line
  and column.
- `effects` uses the shape of the edits in kernel.md §8. A new document
  lists everything under `added`.
- `PrintResult.lines` has the same shape for the printed text.
  `PrintResult.issues` holds the printer's warnings (§6.4).

## 2. Lexer and grammar subset

### 2.1 Tokens and input replacements

A line is split into tokens; replacements happen on tokens, so every token
keeps the column where it starts in the line as typed:

| typed | token | typed | token |
|---|---|---|---|
| `\|\|` | `∥` | `<=` | `≤` |
| `_\|_` | `⟂` | `*` | `·` |
| `<)` | `∠` | the word `in` | `∈` |
| `>=` | `≥` | the word `deg` | `°` |
| `−` (U+2212) | `-` | | |

- A **name** is a letter (Unicode category L*) followed by letters, decimal
  digits, `_ { }`, subscript digits `₀…₉`, primes `'`, and `.` before a
  letter. So a registry operation ID such as `point.midpoint` is one name.
  A name stops before `_|_` (`AB_|_CD` is `AB ⟂ CD`).
- A **number** is `12`, `1.5`, `.5`, `2e-7` or `1E+3`. It has no sign; the
  grammar handles `+` and `-`.
- A **symbol** is one of `( ) , = ∠ ° · + - / ^ < > ≤ ≥ ∥ ⟂ ∈ | √ ≠ ∧ ∨ ; : [ ] !`.
- `#` starts a comment that runs to the end of the line.
- Any other character is a `syntax` error at its column.

### 2.2 Lines

```text
line   ::= [ names "=" ] right [ "#" text ]
names  ::= name { "," name }
right  ::= Command "(" [ arg { "," arg } ] ")"
         | "(" number "," number ")"          → point.free
         | number [ "°" ]                       → number.free
         | "∠" name                             → angle.by_points (∠ABC: A, B, C)
arg    ::= name | number [ "°" ] | "не" name | "∠" name | "(" number "," number ")"
number ::= [ "+" | "-" ] NUMBER
```

- A command name may be several words (`Серединный перпендикуляр`).
- Empty lines are ignored. A line may end in `\r`.
- Lines run top to bottom. An argument can only name an element made by an
  earlier line; a name made further down is `unknown_name` («D задаётся
  ниже, в строке 5»).
- `°` turns a literal into radians: `(v · π) / 180`, i.e.
  `v * math.pi / 180.0`.
- From 1.9.0a3 a comment is a step caption (web decision №17, §12.4): a
  comment at the end of a line is the `text` of its step, a line that is
  only a comment opens an explicit group. `comment_dropped` is gone.

### 2.3 Outside the subset

The following are refused with `forbidden` and the message «… будет позже»
(or «будут позже»). The line is skipped.

| input | example |
|---|---|
| a bare statement | a top-level `≠ ∥ ⟂ ∈` (it goes into `Условие(…)` or `Проверить(…)`, §12) |
| equations | `x = 3`, `y = 2x + 1`, two `=` on a line |
| functions | `f(x) = …` |
| inequalities | a top-level `< > ≤ ≥` |
| expressions other than a number | `r = 2 + 1`, `Окружность(A, 2·r)` |
| `key = value` arguments | `Точка(c, t = 0.5)` |
| `около A` | hint «не A» (web decision №8; `intersect.nearest` is β) |
| a copy of an element | `b = A` |

## 3. Names, pairs and hidden operations

An argument that is a name resolves in this order:

1. **An element in scope.** The element's `displayName` is compared by
   `name_key` (`_{x}` ≡ `_x`, as `rename` compares). An element is in scope
   when an earlier line made it.
2. **A pair of points** (web decision №5). The name splits into two names
   of points in scope: `BC` → `B`, `C`; `A_1B` → `A_1`, `B`. Exactly one
   split must exist. More than one split is `ambiguous_pair`, with the
   options as the hint (`A, BC или AB, C`). No split is `unknown_name`.
3. **`∠ABC`** splits the same way into three points.

**An element name wins over a pair split.** If `BC` is an element, `BC`
means that element even when `B` and `C` are points. This deviates from §11
of the kernel spec and §5.4 of the L2 plan, where both readings together
were the error `ambiguous_pair`. The reason: elements named after their
points are common (lines imported from GeoGebra are called `AB`), and with
the error the printed text of such a document would not read back, because
every line that refers to `BC` would fail.

Instead, both directions flag such a name with the warning `ambiguous_name`:

- **the parser** — at a name on the left of a line without errors, when the
  element's name also splits into two names of points of the resulting
  document. The points may be made on any line, above or below;
- **the printer** — at the same place in its text: the name on the left of
  the line that defines the element.

The warning comes once per name, where the name is defined, not at each use.
`parse_commands(print_commands(doc).text).issues` holds the same
`ambiguous_name` warnings as `print_commands(doc).issues`, at the same lines
and columns. The web highlights the name; to refer to the pair instead, the
user renames the element.

A pair becomes a hidden operation. If the argument's position takes
`segment` but not `line` (a `segment` slot, a list of segments), the pair
becomes `segment.by_points(B, C)`. Otherwise (`line`, `linear`, `curve`,
`path`) it becomes `line.by_points(B, C)`. `∠ABC` becomes
`angle.by_points(A, B, C)`. A hidden element has `displayName: ""` and
`appearance[id].visible = false`.

Hidden operations are reused, in this order:

- a visible element in scope made by the same operation from the same
  points in the same order (`l = Прямая(B, C)` and then `Проекция(A, BC)`
  references `l`);
- an existing hidden element of the same operation and points.

A hidden operation lives as long as something references its element. When
nothing does, it goes (§8).

`не A` is the known point of an `other_than` intersection:
`Пересечение(c, d, не A)` → `intersect.other_than(c, d, known = A)`.

## 4. Lexicon and overloads

### 4.1 Format `animageo-lexicon/v1`

```json
{"format": "animageo-lexicon/v1",
 "commands": [
   {"name": "Середина", "aliases": ["Midpoint"], "op": "point.midpoint"},
   {"name": "Параметр", "aliases": ["Ползунок", "Slider"], "op": "number.free",
    "form": ["$input", "min", "max", "step"], "minArgs": 0},
   {"name": "Точка", "aliases": ["Point"], "op": "point.on_path", "form": ["path", "$input"], "minArgs": 1}
 ]}
```

- An entry pairs a name, and its aliases, with a registry operation. One name
  may stand for several operations (overloads).
- `form` is the order of the positional arguments. Each item is an input
  slot, a param, or `$input` (the value of a free op's input). By default
  `form` is the input slots in registry order, then the params. Every input
  slot must be in `form`. A free op whose input has no default (`point`)
  needs `$input`. After a list slot, only params and `$input` may follow.
- `minArgs` is how many leading positions are required. By default it is
  every position up to the last one that cannot be left out. A param with
  `optional` can be left out, and so can a `$input` with a default:
  - `pathParameter` defaults to the path's `paths.<type>.default`;
  - `number` defaults to the op's `min`, or `0`.
- Names compare without case and without whitespace, so «Серединный
  перпендикуляр» equals «СерединныйПерпендикуляр». Aliases compare the same
  way.
- A registry operation ID (`point.midpoint`) is also a command name, written
  exactly. Its positions are the input slots, then `$input` of a free op,
  then the params. The printer falls back to it for an operation the lexicon
  does not name.
- `lexicon_hash` is `sha256:` of the canonical JSON (kernel.md §3) of the
  lexicon.

### 4.2 Checks (`lexicon_problems`)

`Lexicon(data)` raises `LexiconError(problems)` when `lexicon_problems(data)`
is not empty. It reports:

- a wrong format, unknown keys, or an empty name or alias;
- an op that is not in the registry;
- a `form` that names an unknown slot, repeats a slot, leaves out an input
  slot, lacks a needed `$input`, or puts an input slot after the list slot;
- a `minArgs` out of range, or one that lets a required position be left
  out;
- two entries under one name that take the same arguments, where neither
  set contains the other (an ambiguous overload);
- an entry under a name that an earlier entry fully covers (unreachable).

### 4.3 Resolution

Every argument has a kind:

- an element type (`point`, `segment`…);
- a number literal or a point literal `(x, y)`;
- `не A`, a pair `BC`, or `∠ABC`.

A position accepts these kinds:

| position | accepts |
|---|---|
| input slot of type T | T and the members of family T (registry `families`) |
| … if those include `number` | also a number literal |
| … if they include `segment` or `line` | also a pair |
| … if they include `angle` | also `∠ABC` |
| the `known` slot of `intersect.other_than` | only `не A` |
| param | a number literal |
| `$input` | a point literal for `point`, a number literal otherwise |

A list position takes the run of non-literal arguments that starts at it.
The literals after the run go to the params and `$input` that follow the
list.

The candidates are the lexicon entries under the command's name, in lexicon
order. The first entry that takes the number of arguments and accepts every
argument wins. `intersect.line_circle` also accepts its two arguments the
other way round (`Пересечение(c, AB)`).

When no entry wins:

- if no entry takes that many arguments, the error is `arity` at the command;
- otherwise it is `type_mismatch` at the first argument that does not fit,
  measured against the entry that fits best, with a message like
  «Пересечение: аргумент 2 — точка, ожидается прямая, отрезок или луч».

Either way, the hint is the signature, e.g. `Окружность(точка, точка)`.

An unknown command is `unknown_command`. Its hint is the nearest command
name within two edits (Levenshtein, case and spaces ignored), if any.

A literal goes into the document as a literal argument (kernel.md §1). A
`$input` value goes into `inputs`. A left-out `$input` takes its default:
the path's default parameter, or the `min` of `number.free`.

### 4.4 The default lexicon

`lexicon.v1.json`, 35 entries: 26 for the operations of L0–L2 stages 1–2 and
9 for L3 (1.9.0a1). `Биссектриса` has two entries, resolved as in §4.3:
`(A, B, C)` is the angle bisector, `(vertex, side)` the bisector of a
triangle:

| name | aliases | op |
|---|---|---|
| Точка | Point | `point.free` (`$input`), `point.on_path` (`path, $input?`) |
| Середина | Midpoint | `point.midpoint` |
| Пересечение | Intersect, ВтороеПересечение | `intersect.line_line`, `intersect.line_circle`, `intersect.circle_circle`, `intersect.other_than` |
| Проекция | ОснованиеПерпендикуляра | `point.projection` |
| Отрезок, Прямая, Луч, Вектор | Segment, Line, Ray, Vector | `segment.by_points`, `line.by_points`, `ray.by_points`, `vector.by_points` |
| Параллельная | Прямая, Line | `line.parallel` |
| Перпендикуляр | PerpendicularLine | `line.perpendicular` |
| СерединныйПерпендикуляр | СрединныйПерпендикуляр, PerpendicularBisector | `line.perpendicular_bisector` |
| Биссектриса | AngleBisector | `line.angle_bisector` |
| Окружность | Circle | `circle.center_point`, `circle.center_radius` |
| ОписаннаяОкружность | Окружность, Circle, Circumcircle | `circle.three_points` |
| ВписаннаяОкружность | Incircle | `circle.incircle` |
| Многоугольник | Polygon | `polygon.by_points` |
| Параметр | Ползунок, Slider | `number.free` (`$input?, min?, max?, step?`) |
| Угол | Angle | `angle.by_points` |
| ОтметкаРавныхОтрезков, ОтметкаРавныхУглов, ПрямойУгол | — | `mark.equal_segments`, `mark.equal_angles`, `mark.right_angle` |
| Высота | Altitude | `triangle.altitude` (`vertex, side`) |
| Медиана | Median | `triangle.median` (`vertex, side`) |
| Биссектриса | AngleBisector | `triangle.bisector` (`vertex, side`) |
| ТочкаПересеченияМедиан | Центроид, Centroid | `triangle.centroid` |
| Инцентр | ЦентрВписанной, Incenter | `triangle.incenter` |
| ЦентрОписанной | Circumcenter | `triangle.circumcenter` |
| Ортоцентр | Orthocenter | `triangle.orthocenter` |
| ЦентрВневписанной | Excenter | `triangle.excenters` |
| ГМТ | Локус, Locus | `locus.of_point` (`point, mover`) |

`side` takes a segment, a line, a ray or a pair `BC`; the pair becomes a
hidden `line.by_points` (§3), whose points are the ends of the side
(kernel.md §11.1).

## 5. Default names

`naming.py` ports the web app's `canvas/document/naming.ts`. A new output
without a name on the left gets the first free name for its type, where
"free" compares by `name_key`:

| type | names |
|---|---|
| point | `A … Z`, then `A_1 … Z_1`, `A_2 …` |
| line, segment, ray, vector, number | `a b c d f g h j k l m n o p q r s t u v w` (no `e i x y z`), then `a_1 …` |
| circle | the same letters starting from `c` |
| polygon | `t`, then `t_1`, `t_2 …` |
| angle | `α β γ δ ε ζ η θ κ λ μ ν ξ π ρ σ τ φ χ ψ ω`, then `α_1 …` |
| mark, hidden elements | `""` |

**Sides of a triangle.** When all three vertices are single uppercase
letters, a side gets the school name: the lower case of the vertex opposite
it. `side.i` runs from vertex i to vertex i+1, so ABC gets `c, a, b`. A side
takes its school name only if that name is free and is one of the lower
letters above; otherwise it takes the next free name. EFG gets `g, a, f`,
because `e` is not used. Polygons with other vertices get the next free
names in order.

**Taken names.** These names are not free:

- the names in the document;
- every name the text writes on the left of `=`, anywhere in the text
  (so a default name never takes a name a later line asks for).

In edit mode, the names of operations that lost their line are free (§8).

**Name rules on the left side:**

- a name must follow the `rename` grammar (kernel.md §8), else
  `invalid_name`;
- a name another element has is `name_taken`, compared by `name_key`
  (`A_{1}` is taken when `A_1` exists), with a free name as the hint: the
  same letters with the next `_k`, so `A` gives `A_1`;
- the same name twice on one line is also `name_taken`;
- more names than outputs is `arity`.

The left side binds outputs in slot order and may be shorter than the
outputs (a prefix). In a new document every output gets an element; the
outputs the left side does not name get default names.

## 6. Printer

### 6.1 Lines

- **Order.** One line per operation, in Kahn order with ties by operation
  ID (`kernel.evaluate._order`, the topological order of kernel.md §8). So
  the IDs decide the order of independent lines, and clients must give
  time-ordered IDs (§1).
  Hidden pair and `∠ABC` operations get no line. Their elements appear in
  arguments as `BC` and `∠ABC`. (Web decision №7; `seq` and the order of
  steps come with L3.)
- **Left side.** The output names in slot order, up to the last slot that
  has a name or is used. A slot in the middle without a name gets the default
  name that parsing would give it; `_` is not used. An operation without
  named or used outputs (a mark) prints no left side.
- **Short forms:**
  - `point.free` prints `A = (x, y)`;
  - `number.free` without params prints `r = 3`;
  - `number.free` with params prints `r = Параметр(v, min, max, step)`, with
    trailing absent params left out;
  - `point.on_path` prints `P = Точка(c, t)`;
  - a visible `angle.by_points` prints `α = Угол(A, B, C)`.
- **Entry.** The printer tries the lexicon entries for the operation in
  order, then the op-ID fallback (§4.1). It prints the entry's name, never an
  alias. The first entry whose printed call reads back, through the same
  resolution (§4.3), as the same operation with the same arguments wins.
- **Numbers.** See §6.2. A `$input` that the form allows to be left out is
  still printed.

### 6.2 Numbers

`format_number` prints the shortest form that reads back as the same double
(Python `repr` is JavaScript's shortest round-trip form):

- decimal when `1e-6 ≤ |x| < 1e15`: `0.30000000000000004`, `2`, `-1.5`;
- exponential otherwise, in JavaScript style: `1.5e-7`, `2e+21`;
- `-0.0` prints as `0`.

### 6.3 Reading back

`parse_commands(print_commands(doc).text)` rebuilds the structure of `doc`:
the operations, their arguments (up to IDs), the names, the input values and
the hidden pairs. The exceptions:

- an output that `doc` leaves unbound comes back bound, with a default name;
- the cases of §6.4.

Edit mode keeps more: `parse_commands(print_commands(doc).text, base=doc)`
gives empty `effects` and the same document. This holds for every scene of
`parity/v1` and every document of the commands fixtures; a scene with a
`number.expression` reads back with the error `forbidden` at its lines (a
`text.free` with `syntax`), and the edit keeps those operations (a failed
line keeps the operation it names).

### 6.4 Warnings

| code | when | what is printed |
|---|---|---|
| `ambiguous_name` | an element's name on the left also reads as two names of points of the document (§3); the column is the name's | the name as it is; in arguments it means the element |
| `unprintable_pair` | a hidden pair or angle would not read back as itself. Its points may have no names, or `BC` may not split one way. An element may be named `BC`. The position may make the other pair op. Or a visible element made the same way would be taken instead | `BC` anyway; it may not read back |
| `unprintable_params` | a param after a left-out one (for example `max` without `min`): the form has no gap | the nearest form the lexicon has; the param after the gap is dropped |
| `unprintable_operation` | the op is not in the registry, or the operation does not fit its record | `opid(args)` in registry slot order |
| `unprintable_operation` | a `number.expression` (1.8.1a5): the grammar has no expressions yet | the formula, `e = sqrt(a) + b^3` ([expr.md](expr.md) §4); it reads back as `forbidden` |
| `unprintable_operation` | a `text.free` (1.8.1a5): the grammar has no strings yet | `t = Текст("a = {0}", A, a)` — the template as a JSON string, the anchor, the refs (`decimals` is not printed); it reads back as `syntax` at `"` |

## 7. Issues

| code | severity | when |
|---|---|---|
| `syntax` | error | an unknown character, unbalanced parentheses, a missing comma, an empty argument, no name before `=` or nothing after it |
| `forbidden` | error | outside the subset (§2.3) |
| `unknown_command` | error | no lexicon entry and no op ID with this name |
| `unknown_name` | error | no element in scope, and no pair split (§3) |
| `arity` | error | no entry takes this many arguments; more names on the left than outputs |
| `type_mismatch` | error | an argument does not fit (§4.3); in edit mode, a refused `redefine` with that code |
| `ambiguous_pair` | error | a pair or `∠ABC` splits more than one way |
| `name_taken` | error | a name on the left belongs to another element, or repeats |
| `invalid_name` | error | a name on the left breaks the `rename` grammar |
| `unprintable_condition` | warning | a condition the printer cannot say (1.9.0a3) |
| `unsupported_condition`, `receiver_not_free`, `receiver_is_ancestor`, `too_many_conditions` | error | an `Условие(…)` line (§12.2) |
| `ambiguous_name` | warning | a name on the left also reads as two names of points of the document; the name means the element (§3). The printer gives the same warning |
| `unprintable_pair`, `unprintable_params`, `unprintable_operation` | warning | printer only (§6.4) |

In edit mode a refused `redefine` (§8) reports its own code: `slot_conflict`,
`type_mismatch`, `cycle`, `missing_input`, or a `validate` code. The message
is in Russian and names what blocks the change.

- `line` and `column` are 1-based.
- `column` counts code points of the line as typed, before replacements:
  `<)ABC` has `∠` at its first column.
- An error points at the token that caused it. For a call that cannot be
  resolved, that is the command; for a bad argument, the argument.
- `message` is Russian text for the user, and `hint` (optional) is a
  suggestion.
- Fixtures compare `code`, `line`, `column` and `severity`; they do not
  compare `message` or `hint`.

## 8. Edit mode

`parse_commands(text, base=doc)` changes `doc` to match the text and keeps
IDs.

**Matching lines to operations:**

- A line claims the operation that produced the element named first on its
  left, if that element is in `base`.
- A line without such a name claims an operation of `base` that has no named
  outputs, by definition. It first looks for the same op with the same
  arguments, then for the same op with the same inputs but other params (a
  mark whose count changed keeps its ID).
- A line whose first name is new makes a new operation. Renaming an element
  is an explicit `rename`, not an edit of the text.

**Applying a line:**

- **Typed back unchanged.** The line has the same tokens as the printer's
  line for its operation, and every reference is in scope. The operation
  stays exactly as it is, even where the printer could not say everything
  (a param after a gap, a pair that does not read back).
- **Same definition.** Only the input value changed (a moved point, a new
  number): the value is written to `inputs`.
  - A new name in a later position renames that output.
  - A name for a slot that had no element adds the element.
- **Changed definition.** The edit is `native.redefine`.
  - The old outputs named on the left go to the slots of their positions.
  - An old output whose slot the new op lacks, or whose slot another name
    takes, is dropped together with its dependents (warning
    `output_removed` in `effects.warnings`).
  - New slots get default names.
  - If `redefine` refuses, the line becomes an error with redefine's code
    (§7) and the operation stays as it was.
- **Errors.** A line with an error keeps its operation unchanged.

**Names of unclaimed operations.** The names of operations that no line
claimed are free. A line may take such a name; the old element then loses
it.

**Deleting.** At the end, every operation of `base` that no line claimed goes,
together with everything built on it (`native.delete`,
`mode="operation"`). Hidden pair operations go when nothing references them.
Everything that went is listed in `effects.removed`; the web asks for
confirmation before applying it.

**Registry version.** `operationRegistryVersion` rises to the current
version when an operation needs a newer one (`since`).

**Effects** compare `base` with the result, section by section. Each list is
sorted; the shape is kernel.md §8.

## 9. Fixtures

`animageo/native/parity/v1/commands/` holds 11 files `animageo-commands/v1`
(185 cases) and `naming.json` (`animageo-naming/v1`: 20 names, 8 side cases
and 11 name keys), generated for the default lexicon.

```text
{"format": "animageo-commands/v1", "id": "parse_points",
 "lexiconHash": "sha256:…", "registry": "1.3", "generatedBy": "animageo 1.8.1a4.dev0",
 "cases": [{"name": "…", "text": "A = (0, 0)\n…", "base": null | {document},
            "expect": {"operations": [{"op", "args", "outputs", "hidden"}],
                       "inputs": {"<name>": {…}},
                       "lines": [{"line", "elements": ["<name>", …]}],
                       "issues": [{"code", "line", "column", "severity"}],
                       "effects": {…},            // cases with base only
                       "print": "…",
                       "printIssues": [{"code", "line", "column", "severity"}]   // when not empty
                      }}]}
```

- **Templates.** The catalog is written as templates: `{point.midpoint}`
  is the first name the lexicon gives the op (its ID when the lexicon has
  none), and `{point.midpoint:alias}` is that entry's first alias (its name
  when it has none). One catalog therefore yields the fixtures of any
  lexicon, and the browser parser is checked against the fixtures of its own
  lexicon.
- **IDs.** A replay must use `documentId` `"doc"` and the counter IDs
  `o1, o2…` (operations) and `e1, e2…` (elements), skipping IDs already in
  `base`. `base` is a full document (parsed from a base text the same way).
- **Normalization.**
  - IDs become display names, and hidden elements become `#1, #2…` in order
    of appearance.
  - Operations follow the lines, with a line's hidden operations before it.
  - Arguments are names, lists of names, or literal values.
  - `effects` keeps the raw IDs, which are deterministic thanks to the
    counters.
- **`print`** is the printer's text for the parsed document, and
  `printIssues` its warnings.
- **Naming cases.** `naming.json` has `cases: [{name, type, taken, expect}]`
  for `next_name`, `sides: [{name, vertices, taken, expect}]` for
  `polygon_side_names` and `keys: [{name, key}]`: raw names with their
  `name_key` (`A_{1}` → `A_1`, `A₁` stays `A₁`), for a client that ports
  `name_key`. `taken` holds raw names; a client compares them by key.

**Contents of the set:**

| file | cases |
|---|---|
| `parse_points` | 15 |
| `parse_lines` | 24 |
| `parse_intersections` | 12 |
| `parse_circles` | 15 |
| `parse_angles_marks` | 12 |
| `pairs` | 9 |
| `overloads` | 7 |
| `names` | 12 |
| `numbers` | 5 |
| `parse_triangle` | 27: the eight `triangle.*` ops by pair, by named segment and by alias, unnamed outputs, `ГМТ` on a segment, a circle and a slider (1.9.0a1) |
| `errors` | 37: every error code with its column, plus `forbidden` variants and columns before replacements |
| `edit` | 17: unchanged text, moved point, changed number, redefine (and refused, and to a free op), deleted line (and cascade), new line, new name, mark count, removed mark, secondary names, error keeps the operation, swapped outputs, redefine below, reused free name |

## 10. Command line

```text
python -m animageo.native commands fixtures [--lexicon <file> -o <dir>] [--check]
python -m animageo.native commands parse <text file | -> [--lexicon <file>] [--base <doc.json>]
                                         [--document-id <id>] [--canonical]
python -m animageo.native commands print <doc.json> [--lexicon <file>]
```

- **`fixtures`** writes the set for a lexicon (web decision №9). Without
  `--lexicon` it writes the library's default directory. With `--lexicon`,
  `-o` is required; the web passes its generated lexicon and its
  `fixtures/commands/`. `--check` compares instead of writing (ignoring
  `generatedBy`) and exits 1 with a hint when the set is out of date.
- **`parse`** prints `{document, effects, lines, issues, conditionRequests, queries}` as JSON and the
  issues on stderr. It exits 1 when there are errors.
- **`print`** prints the text and the warnings on stderr. It accepts a
  document or a parity scene (`animageo-parity/v1`).
- An unusable lexicon, or a missing or unreadable file, exits 2.

## 11. Known limits

- `in` and `deg` are words of the notation (§2.1), and `x` or `y` alone on
  the left is an equation. These names cannot be typed, although the
  document allows them; the printer prints them anyway.
- Lines that do not depend on each other print in operation-ID order (§6.1),
  hence the rule of §1: IDs grow in creation order. With other IDs a line
  may print below a line that the user then makes refer to it; that
  reference is `unknown_name` until the line moves up. Explicit order comes
  with `seq` (L3).
- `number.expression` prints as its formula, which the grammar refuses
  (`forbidden`, «выражения будут позже»); expressions in «Команды» come with
  the expression language v2. `text.free` prints as `Текст("…", A, …)`,
  which the lexer refuses at `"` (`syntax`).
- A param after a gap (`number.free` with `max` but no `min`) does not print
  (`unprintable_params`). Edit mode still keeps it, as long as the printed
  line comes back unchanged.
- Re-parsing the text of a document with unbound outputs in the middle binds
  them (§6.3).

## 12. Conditions, checks and steps (1.9.0a3, plan L3 §4)

### 12.1 Grammar

```text
line      ::= … | "Условие" "(" statement [ "," "двигать" point ] ")"
            | "Проверить" "(" statement ")" | CheckCommand "(" args ")"
            | "Отношение" "(" obj "," obj ")"
statement ::= expr ("=" | "≠") expr | obj ("∥" | "⟂") obj | point "∈" obj
            | obj "касается" obj | CheckCommand "(" args ")"
expr      ::= + − · / ^ (right-associative), unary minus, ( … ), numbers with "°",
              "π", "|" obj "|", "∠" ABC, "∠" α, "√" atom, sqrt sin cos tan … "(" … ")",
              names of numbers and angles
obj       ::= the name of an element | a pair of points (AB)
```

- The words come from the lexicon: `keywords` (`condition`, `check`,
  `move`, `touches`, `not`, `near`, plus `given` «Дано» and `relation`
  «Отношение» of 1.9.0a3); the first word of a key prints. Without a
  lexicon (`parse_line(tokens, n)`) `Условие` stays `forbidden` as in 1.8.
- Check commands are lexicon entries with `check` (a statement kind) in
  place of `op`: `ПроверкаПараллельности`/`AreParallel` (`parallel`),
  `ПроверкаПерпендикулярности`/`ArePerpendicular`, `ПроверкаКасания`/
  `IsTangent`, `ПроверкаПринадлежности`/`IsOnPath` (`on`),
  `ПроверкаКоллинеарности`/`AreCollinear`, `ПроверкаКонцикличности`/
  `AreConcyclic`, `ПроверкаКонкурентности`/`AreConcurrent`,
  `ПроверкаРавенства`/`AreCongruent` (`congruent`),
  `ПроверкаСовпадения`/`AreEqual` (`coincident`). A line of one reads as
  `Проверить(…)`; a check name may not be a command name.
- A name of an element wins over a pair (as in arguments); `A = B` of two
  points is `coincident`; a bare segment name in an expression is
  `type_mismatch` with the hint `|s|`. The statement is checked by
  `statement_problems` (`type_mismatch`).
- `около A` stays `forbidden` (W2 №8).

### 12.2 The parse result

`ParseResult(document, effects, lines, issues, conditionRequests, queries)`:

- `Проверить(…)` — a `conditions[]` entry `{id: "c<n>", seq, mode: "check",
  statement}` (the smallest free `n`; `seq` — after the largest of the
  document), and a line `{line, operationIds: [], elementIds: [],
  conditionId}`.
- `Условие(…)` — a request `{line, kind, statement, receiver}`; `receiver`
  is the one of `двигать`, else the default (plan §3.5) — the parse judges
  it on the document without the conditions of the text applied (edit mode:
  `printable_document`, §12.3). Errors without values: `unsupported_condition`
  (no recipe, or none moves the named point), `receiver_not_free`,
  `receiver_is_ancestor`, `too_many_conditions` (constraints plus the
  requests and the kept conditions on the receiver), `ambiguous_pair`;
  `no_intersection_now` only when applied.
- `Отношение(a, b)` — `{line, kind: "relation", a, b}` in `queries`
  (`native.relation` answers it); nothing goes into the document.
- `apply_condition_requests(doc, requests, *, id_factory=None, marks=True)
  → RequestsResult(document, results)` carries the requests out in order
  (computational: the sandbox; the browser — the TS copy): `apply` —
  `apply_condition` with `source: "command"` and the receiver; `release` —
  `release_condition` at the current position; `replace` — both or neither;
  `move` — the receiver's parameter becomes the projection of `point` onto
  its place (a receiver on two places has no freedom). A refused request
  changes nothing; `results` — `[{line, kind, conditionId, refusal}]`.

### 12.3 The printer

- `printable_document(doc)`: each receiver of a construct condition is
  defined by its `receiverOrigin` (ID and `seq` kept), the places of
  conditions and the automatic marks (`origin.kind = "auto"`, helpers
  included) are gone, and so are the construct conditions and the
  `condition` steps. Lines are printed from it.
- Order: the steps of `native.steps` of that document; inside a step — its
  operation order (order key, then ID). For a document without `seq`,
  `steps` and conditions the order is the 1.8 one.
- An explicit `given`/`group` step with a `title` or with ≥ 2 printed
  operations gets a heading `# <title>` (no title: `# Дано` for `given`, `#`
  for a group); its `text` goes to the end of its first line (`  # text`).
  After a group with a heading, a blank line closes it before the next
  printed line that is not a heading.
- `Условие(…)` and `Проверить(…)` go right after the step where their last
  participant is made (a condition with a participant that is not printed —
  at the end), among themselves by `seq`, then ID. `двигать X` is printed
  when the receiver is not the default one on the printable document.
- Printer lines get `{line, operationIds: [], elementIds: [], conditionId}`
  for condition lines; headings and blank lines have no entry.

**Properties** (tests on every scene and fixture document):
`parse(print(doc), base=doc)` ≡ `doc` byte for byte, without requests;
`parse(print(doc))` + `apply_condition_requests` ≡ `doc` by structure and
conditions, inputs equal but for the parameters of receivers (a release
keeps the current position).

### 12.4 Steps from comments

- A line that is only a comment opens an explicit group: its text is the
  `title` (`# Дано`/`# Given` — kind `given`, no title; a bare `#` — no
  title). The group lasts to the next comment line or a blank line.
- A comment at the end of a line is the `text` of the step of its operation
  (inside a group — the group's text; several are joined with `; `); outside
  a group the operation becomes an explicit one-operation step.
- A line's hidden pairs join its group (the first group that uses them).
  Condition and check lines inside a group do not join it. A group without
  operations is dropped. IDs: `s<n>` (the smallest free), in edit mode the
  ID of the base step that holds the group's first operation.
- Edit mode: when the text shows the same groups as `print(base)` (titles,
  texts, printed operations), the steps of `base` stay as they are
  (`given`/`group` kind, hidden operations, one-operation steps without a
  caption); otherwise they are rebuilt from the text.
- `apply_condition` takes the receiver's operation out of its explicit step
  (it goes to the condition's step; staying would make the steps cyclic).

### 12.5 Edit mode with conditions

- The places of the base's conditions and its automatic marks have no
  lines and stay. A receiver's line is its `receiverOrigin` line: typed back
  unchanged — the condition's realization stays; a changed point literal —
  a `move` request and the new `receiverOrigin` in every condition of that
  receiver (the operation stays); another definition — an ordinary
  redefinition (`redefine` around conditions).
- An `Условие` line matches a base construct condition by the statement
  with element IDs (and the receiver, when `двигать` is written): unchanged —
  kept, no request; otherwise `replace` of an unmatched base condition with
  the same receiver, else with the same statement, else `apply`; a base
  condition without a line — `release` (requests go releases first, then by
  line). An `Условие` line with an error keeps one unmatched condition (in
  print order) from release.
- `Проверить` lines match base check entries by statement; unmatched base
  checks are removed, new ones added. `effects` lists `conditions` under
  `added`/`removed`/`modified` when they change.

### 12.6 Lexicon and fixtures

- The default lexicon names every op of the registry but `number.expression`
  and `text.free` (registry 1.4 ops got names of the matrix: `Площадь`,
  `Касательная`, `Поворот`, `ЛучПодУглом`, …), plus the check commands and
  `keywords`.
- Fixtures of L3 (`animageo/native/commands/fixtures_l3.py`):
  `parse_l2a4` (two cases per 1.4 op), `conditions` (13 recipes × 3),
  `condition_errors`, `checks` (each statement kind × 2, check commands,
  queries), `comment_steps`, `print_order` (steps and `seq`),
  `edit_conditions`. A base may hold conditions (parsed, then its requests
  carried out); `expect` adds `conditions`, `steps`, `conditionRequests`,
  `queries` (IDs as names, operations as `@<index>`) and `afterRequests`
  (`print`, `results` with the refusal code and the recipe). 246 cases in
  7 files (458 in all). The cases are written with the default names;
  `localize` renames commands, check commands and keywords for another
  lexicon (`commands fixtures --lexicon`).
