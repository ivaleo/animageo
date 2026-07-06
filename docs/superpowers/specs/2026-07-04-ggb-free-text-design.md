# GeoGebra free-text objects — design

**Date:** 2026-07-04
**Status:** approved, implementing

## Problem

AnimaGeo does not render GeoGebra *text* objects (free static/mathematical
labels and dynamic-value texts). Confirmed on `test_text.ggb`:

- LaTeX text `надпись1` (`"$math=\sqrt2$"`) → parser logs *"No implementation
  for expression"* and drops it.
- Plain text `надпись2` (`"text"`) → parsed as `name = "text"` → a bare `str`
  Element → *"unsupported data type str"* → not renderable.

Root cause: there is no `text` element type anywhere — no element class, no
parser branch that builds one, no `_render_text`, no exporter emitters. The
companion `<element type="text">` (position, `isLaTeX`, font, colour) is never
consumed.

## GGB serialization (grounded in the two fixtures)

A text object is a pair:

```xml
<expression label="надпись3" exp="&quot;Площадь = &quot; + t1 + &quot; &quot;"/>
<element type="text" label="надпись3">
    <show object="true" label="false" ev="40"/>
    <objColor r="0" g="0" b="0" alpha="0"/>
    <isLaTeX val="true"/>                     <!-- optional -->
    <font serif="true" sizeM="1" size="0" style="0"/>
    <startPoint x="0.39" y="0.69" z="1"/>     <!-- literal coords -->
</element>
```

Forms that must be handled (all present across `text_static.ggb` /
`text_dynamic.ggb`):

| Case | `exp` | position | latex |
|------|-------|----------|-------|
| static LaTeX | `"$math=\sqrt2$"` | literal coords | yes |
| static plain | `"text"` | literal coords | no |
| dynamic (polygon area) | `"Площадь = " + t1 + " "` | literal coords | no |
| dynamic + anchor + offset | `"элементы: точка " + A + ", сторона " + a + ""` | `<startPoint exp="A">` + `<labelOffset x="25" y="45">` | no |

Key facts:

- **Concatenation** uses top-level `+` joining **string literals** and **bare
  object references** (no parentheses): `"..." + t1 + " "`.
- **Object value is type-dependent** (GeoGebra `toValueString`): Polygon→area,
  Segment→length, Point→`(x, y)`, number/measure→number, angle→`n°`,
  boolean→`true/false`.
- Numbers are rounded to the kernel `<decimals val="1">` setting with
  **trailing-zero stripping** (`2.0`→`2`, `2.50`→`2.5`).
- `<startPoint>` is **either** literal `x/y/z` coords **or** `exp="A"`
  (anchor to a point object — position tracks the point live).
- `<labelOffset x y>` may accompany an anchored text: final position =
  anchor coords + offset (GGB screen px, y-inverted — reuse
  `ggb_label_offset_to_style`).
- `<font serif>` → serif flag; `<font size>`/`sizeM` → font size; `<objColor>`
  → text colour; `<show object>` → visibility.

## Design

### 1. `Text` element (`geo/lib_elements.py`)

```python
class Text:
    def __init__(self, segments, position=None, anchor_point=None,
                 is_latex=False, serif=False):
        self.segments = segments          # [('str', s) | ('obj', name)]
        self.position = position          # np.array([x, y]) or None
        self.anchor_point = anchor_point  # element name or None
        self.is_latex = is_latex
        self.serif = serif
```

Module-level pure helpers (so renderer and both exporters share one source of
truth):

- `format_object_value(data, decimals) -> str` — type dispatch above.
- `resolve_text_string(construction, text, decimals) -> str` — join segments;
  `obj` segments look up `construction.element(name).data` (live) and format.
  Missing/unresolvable segment → empty string + `logger.warning`.
- `resolve_text_position(construction, text) -> np.array([x, y])` — literal
  `position`, or anchor point's current coords. (Pixel offset is applied by the
  renderer/exporter, which own `ptUnit`.)

`Text` is re-exported from `lib_elements` so
`type(elem.data).__name__ == 'Text'` drives dispatch, matching Conic/Function.

### 2. Parser (`parsers/ggb_parser.py`)

- Thread kernel decimals: read `<kernel><decimals val>` where gui/kernel are
  parsed and store `constr.ggb_decimals` (default 2).
- **Detect** at the top of the `<expression>` handler:
  `expr_type is None and '"' in expr` ⇒ text. Stash raw `exp` in
  `text_exprs[name]`, `continue` **without** `xelems_left_to_pass` so the
  following `<element type="text">` runs. (Numeric/point expressions never
  contain `"`, so this is unambiguous; it also removes the current
  "No implementation" / str-var mis-parse.)
- **Split** `exp` into segments: top-level `+` split respecting quotes and
  parens. `"..."` → `('str', unescaped)`. Other token → normalized element
  name if it exists → `('obj', name)`; else a compound sub-expression →
  phantom Var via existing `_ggb_parse(constr, f"{ph} = {converted}")` →
  `('obj', ph)`.
- **Create** in the second `<element>` block a `type == "text"` branch:
  parse `<startPoint>` (literal coords → `position`; `exp` → `anchor_point`),
  `<isLaTeX>`, `<font serif>`; build `Element(name, Text(...), fixed=True)`.
- Colour (`objColor`→`label_color`), visibility (`<show>`), font size, and
  `<labelOffset>` flow through the **existing** style pass unchanged.

### 3. Renderer `_render_text(elem, ctx)` (`animageo.py`)

- `content = resolve_text_string(self.geo, elem.data, decimals)`.
- Plain text is LaTeX-escaped; LaTeX text passed through. Build
  `Tex(content, tex_template=RusTex, color=ctx.col_label).set(font_size=…)` —
  the same engine `create_label` uses (Cyrillic + `$…$` math).
- Position: `resolve_text_position(...)` + `label_offset_px` (→ MU via
  `ptUnit_ggb`), then anchor the mobject's **top-left corner** there
  (`mobj.shift(pos - mobj.get_corner(UL))`) — GeoGebra's convention.
- z-index label tier; register `Text` in `_Z_AUTO_BY_TYPE`.
- `style/builtin.json`: add a `text` defaults block (`font_size_px`,
  `label_color`, visible).
- Empty content → return `None` (nothing drawn).

### 4. Exporters

- **TikZ** (`exporters/tikz/`): `emit_text` → `\node[anchor=north west,
  text=<colour>, font=…] at (x,y) {content}`; LaTeX content embedded, plain
  escaped. Register mirroring `_render_*`.
- **JSXGraph** (`exporters/jsxgraph/`): `board.create('text', [x, y,
  content], {...})`; add a `text` element to the `animageo-board/v1` spec
  (`spec.py` + `board.schema.json` + `builder.py` + `style_map.py`
  colour/anchor/layer). Static resolved string + coords is the baseline; an
  anchored text emits the resolved anchor coords.

### 5. Tests (`tests/test_text.py`)

Fixtures committed to `tests/fixtures/text_static.ggb`,
`tests/fixtures/text_dynamic.ggb`.

- Parse: both files → correct count of `Text` elements; segments, `is_latex`,
  `position`/`anchor_point` correct.
- `format_object_value` / `resolve_text_string`: Polygon→area, Segment→length,
  Point→coords, decimals + trailing-zero stripping.
- Render: `_render_text` → non-empty VGroup; top-left corner at the start
  point; anchored text uses point + offset.
- Export smokes: SVG (both files), TikZ (`\node` with content), JSXGraph
  (`text` element / spec entry present).

## Non-goals (YAGNI)

- A DSL factory for authoring `Text(...)` by hand (import-only for now).
- Full GeoGebra `toValueString` for every object type — cover the fixture
  types (Point, Polygon, Segment, number, angle, boolean) + graceful fallback.
- Text box background colour / border (GGB `alpha=0` here → transparent).
