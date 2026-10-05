# `text.free` — text at a point

Registry 1.4 · group `text` · see [kernel.md](../kernel.md).

| | |
|---|---|
| inputs | `text: template`, `anchor: point`, `refs: insertable[]` (min 0) |
| params | `decimals` (default 2) |
| outputs | `text: text` |
| undefined | `invalid_parameter`, `upstream` |
| checks | none |

A text attached to a point (a free-standing text is attached to a hidden
free point), with inserts that follow the construction. The argument
`{"kind": "template", "value": string}` (at most 1000 characters, a
structure rule) is the template: `{k}` inserts item `k` (from 0) of the list
input `refs` — a `number` or a `point` (family `insertable`); `{{` and `}}`
stand for the braces themselves. An insert is a decimal index only (`{0}`,
`{12}`, no sign, no leading zero, no spaces); anything else after `{`, a
lone `}` or an insert outside `refs` is the issue `formula` of `validate`
(path `…/args/text/value`) and the state `error/formula`. Nothing in a
template is evaluated; the result has no markup — escaping for LaTeX or
HTML is the renderer's job.

The value is `{anchor: [x, y], text, parts}`: `anchor` — the point,
`text` — the filled template, `parts` — the pieces in order, `{text}` for a
literal (adjacent literals joined, empty ones left out) and `{ref: k, text}`
for an insert. An insert prints (the rule of GeoGebra values and of the
classic `format_number`):

- a number: the exact binary value rounded to `decimals` places **half to
  even** (`0.125 → 0.12`, `0.375 → 0.38`, `−2.5 → −2` with `decimals = 0`),
  then trailing zeros and a bare point dropped, `−0 → 0`; `abs(v) ≥ 1e15`
  prints its shortest round-trip digits instead (`1e+16`, commands.md §6);
- a number with `unit: "angle"`: `(v · 180) / π` by the same rule, then `°`;
- a point: `(x, y)`, each coordinate by the number rule.

`Number.prototype.toFixed` of JavaScript is not this rule: on an exact tie
it takes the larger magnitude (`(0.125).toFixed(2)` is `0.13`,
`(-2.5).toFixed(0)` is `-3`). A TypeScript kernel rounds the exact value
itself, for example in `BigInt`: `v = m · 2^e` with integers `m`, `e`, then
`m · 10^decimals · 2^e` rounded half to even.

## Value

    if decimals is not a whole number in [0, 10]:   → "invalid_parameter"
    parts = []
    for piece of the template:
        literal s:  parts += {text: s}
        insert k:   parts += {ref: k, text: insert(refs[k], decimals)}
    text = {anchor: [anchor.x, anchor.y], text: join(part.text), parts}

## Degeneracy decisions

None.

## Checks

None.
