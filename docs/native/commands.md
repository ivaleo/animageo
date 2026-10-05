# «Команды» — the text form of a construction document (L2)

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
ParseResult(document, effects, lines, issues)
PrintResult(text, lines, issues)
CommandIssue(code, line, column, message, severity, hint=None)    # .to_dict()
default_lexicon() -> dict           lexicon_problems(data) -> [str]
lexicon_hash(data) -> "sha256:…"    Lexicon(data)  # raises LexiconError(problems)
next_name(type, taken) -> str       polygon_side_names(vertices, taken) -> [str]
format_number(x) -> str             is_helper(doc_data, op_id) -> bool
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
- The default factory is `time_ordered_id()`: UUIDs with the version 7
  layout that increase within the process. The printer breaks ties by
  operation ID (§6.1), so IDs that grow in creation order keep independent
  lines where they were typed. Random IDs (`uuid4`) would shuffle them; a
  host that brings its own IDs should make them time-ordered too.
- `lines` gives one entry per applied line, in text order:
  `{line, operationIds, elementIds}`. `operationIds` starts with the line's
  operation, followed by the hidden operations its arguments created (§3).
  `elementIds` are the outputs of the line's operation.
- A line with an error is skipped: `issues` gets the error, and the document
  is built from the other lines. `issues` is sorted by line and column.
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
- A comment, or a line that is only a comment, gives the warning
  `comment_dropped`. Comments are not kept in the document (web decision
  №17).

### 2.3 Outside the subset

The following are refused with `forbidden` and the message «… будет позже»
(or «будут позже»). The line is skipped.

| input | example |
|---|---|
| conditions and checks | `Условие(…)`, `Проверить(…)`, a top-level `≠ ∥ ⟂ ∈` |
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

An element name wins over a pair split: if `BC` is an element, `BC` means
that element even when `B` and `C` are points.

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

`lexicon.v1.json`, 26 entries for the operations of L0–L2 stages 1–2:

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
- a name another element has is `name_taken`, with a free name as the hint:
  the same letters with the next `_k`, so `A` gives `A_1`;
- the same name twice on one line is also `name_taken`;
- more names than outputs is `arity`.

The left side binds outputs in slot order and may be shorter than the
outputs (a prefix). In a new document every output gets an element; the
outputs the left side does not name get default names.

## 6. Printer

### 6.1 Lines

- **Order.** One line per operation, in Kahn order with ties by operation
  ID (`kernel.evaluate._order`, the topological order of kernel.md §8).
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
`parity/v1` and every document of the commands fixtures.

### 6.4 Warnings

| code | when | what is printed |
|---|---|---|
| `unprintable_pair` | a hidden pair or angle would not read back as itself. Its points may have no names, or `BC` may not split one way. An element may be named `BC`. The position may make the other pair op. Or a visible element made the same way would be taken instead | `BC` anyway; it may not read back |
| `unprintable_params` | a param after a left-out one (for example `max` without `min`): the form has no gap | the nearest form the lexicon has; the param after the gap is dropped |
| `unprintable_operation` | the op is not in the registry, or the operation does not fit its record | `opid(args)` in registry slot order |

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
| `comment_dropped` | warning | a comment (§2.2) |
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
(184 cases) and `naming.json` (`animageo-naming/v1`, 20 names and 8 side
cases), generated for the default lexicon.

```text
{"format": "animageo-commands/v1", "id": "parse_points",
 "lexiconHash": "sha256:…", "registry": "1.3", "generatedBy": "animageo 1.8.1a3",
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
  for `next_name` and `sides: [{name, vertices, taken, expect}]` for
  `polygon_side_names`.

**Contents of the set:**

| file | cases |
|---|---|
| `parse_points` | 15 |
| `parse_lines` | 24 |
| `parse_intersections` | 12 |
| `parse_circles` | 15 |
| `parse_angles_marks` | 12 |
| `pairs` | 8 |
| `overloads` | 7 |
| `names` | 12 |
| `numbers` | 5 |
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
- **`parse`** prints `{document, effects, lines, issues}` as JSON and the
  issues on stderr. It exits 1 when there are errors.
- **`print`** prints the text and the warnings on stderr. It accepts a
  document or a parity scene (`animageo-parity/v1`).
- An unusable lexicon, or a missing or unreadable file, exits 2.

## 11. Known limits

- `in` and `deg` are words of the notation (§2.1), and `x` or `y` alone on
  the left is an equation. These names cannot be typed, although the
  document allows them; the printer prints them anyway.
- Lines that do not depend on each other print in operation-ID order (§6.1).
  With IDs that do not grow in creation order, a line may print below a line
  that the user then makes refer to it; that reference is `unknown_name`
  until the line moves up. Explicit order comes with `seq` (L3).
- A param after a gap (`number.free` with `max` but no `min`) does not print
  (`unprintable_params`). Edit mode still keeps it, as long as the printed
  line comes back unchanged.
- Re-parsing the text of a document with unbound outputs in the middle binds
  them (§6.3).
