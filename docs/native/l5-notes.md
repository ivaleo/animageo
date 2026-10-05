# L5 notes: the spikes C0–C4 (plan L5 §2)

Short conclusions of stage 0, 2026-10-05. The witnesses are
`tests/native/spikes/test_l5_spikes.py`; when one fails, the decision below
is to be revisited.

## C0. Inventory of signatures

- `COMMAND_REGISTRY` has 477 dispatch keys. `convert/dsl_map.json` gives each
  a row: 140 → 47 registry ops, 2 free rows (`point_ii`, `angle_size_i`), 335
  unmapped — 224 `no_registry_op` (conics, functions, coordinates: stage L4;
  predicates `AreParallel`…: checks, not constructions), 70
  `formula_unsupported` (arithmetic of values: `number.expression` is not
  built from classic commands), 41 `unsupported_signature` (the op exists, the
  argument kinds do not: intersections with conics, points by numbers).
  1.10.0a2: 24 of the 70 — the arithmetic of numbers and measures — are
  formula rows of `number.expression` (`mapVersion` 2, `docs/native/import.md`
  §1); 46 stay `formula_unsupported` (points, vectors, angles, segments).
- 38 registry ops have no classic key (`opsWithoutClassic`): marks, triangle
  centres and lines the classic has no command for, `text.free`,
  `number.expression`, the free inputs (37 in 1.10.0a2: `number.expression`
  has formula rows).
- The web seed (60 GGB command names of `headless/translate.py`) is fully
  covered by the rows (`map_problems(seed=…) == []`).
- The classic parser on what it does not know: an unknown command — a
  `Command` without implementation, the output keeps its saved value, the
  diagnostic `unsupported_signature`; 3D elements, CAS cells, lists, buttons,
  images — skipped silently; scripts — ignored (the object is built);
  `Sequence` and other expressions it cannot convert — `expression_parse_error`
  with the saved value. `from_ggb` reports every such object (`3d`, `cas`,
  `list`, `ui_object`, `image`, `script`, `parse_error`, `no_registry_op`) and
  never takes a frozen copy for an editable object.
- Expressions bypassing `safe_sympify`: yes — GGB expressions and command
  arguments became Python for `dsl.run` (`ggb_parser._ggb_parse`), and
  `().__class__.__base__.__subclasses__()` reached `Popen`. Fixed in stage 1:
  `_check_ggb_code` (one assignment, no dunder names, no private attributes,
  no lambda/comprehension/definition). Formula strings already go through
  `safe_sympify`.

## C1. The line of a DSL call

The stack works without changing the AST: from `Construction.add`, the
frames with `co_filename == "<dsl>"` give the line. The innermost such frame
is where the factory is written (inside a user function — the body line),
the outermost one is the top-level statement (the call of the function); a
loop gives the body line on every pass; a call over several lines gives its
first line; `tri, a, b, c = Polygon(...)` and the phantoms of nested calls
give the line of their statement. Outputs are still phantom names (`_1`) at
`add` time — the origin belongs to the `Command` (`Command.origin`), set when
it is added. Stage 2 takes the outermost frame for `line` (the line the user
sees) and may keep the innermost one as well.

## C2. Values in the XML

GeoGebra writes full doubles (`repr` precision) in `<coords>`, `<value>`,
`<matrix>`. On 17 files (the library's 6, the web's 11) every compared value
of the classic-equivalent native document matches within 3.7·10⁻¹⁶·S (points,
lines, circles, arcs, polygons, vectors, angles). `tol.import = 1e-6·S` stays
(the start value of the plan): six orders of magnitude of room, and still far
below a visible difference. Angles: a file with `<angleStyle val="1">` (not
reflex) may hold either the counter-clockwise size native keeps or the size
shown within 0–180° (both seen); the check accepts either (`range` in
`ggb_value`). Arcs and sectors carry only the circle matrix: the check of the
circle in the XML, the angles against the classic value.

## C3. Branches of the classic and native

On 40–100 random cases per command: `tangent_pc` — the first classic output
is always native `tangent.2` (the reverse order); `angular_bisector_ll` — no
static order (56/44); `intersect_cl` — 99/1; `intersect_cc`, `intersect_lc`
— 100/0 on the sample, not by contract. Decision 9 stands: the slot of every
multi-output command is chosen by value (one probe evaluation per document,
cheap); a static order is not used, even where it held on the sample.

## C4. Dynamic topology (for stage 2)

Fifteen deliberate scenarios (`if A.x > 0`, `for i in range(int(B.x))`,
`while`, a user function with a branch, `Point(A.x + 1, 0)`, a conditional
expression, a flag `v = A.x > 0; if v:`): (a) AST taint of names bound by
factories, with the flow through assignments — 15/15; (b) reads of
`ElementProxy` attributes recorded with their `<dsl>` line, classified by
whether the line is a branch or loop condition — 13/15: it misses the
indirect condition (`v = A.x > 0` read on line 2, branch on line 3) and
cannot see `if d > 1` with a measure `d` (the classic DSL raises `TypeError`
on a proxy comparison anyway). Stage 2: (b) to know which values were read,
(a)'s flow to connect a read to a condition; `value_from_python` from (a).
