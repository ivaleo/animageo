# text.block (registry 1.14)

A literal, width-constrained text block at a point. Check support with
`native.has('text.block')`; minimum operation registry version: `1.14`.

| Argument | Tagged kind | Meaning |
| --- | --- | --- |
| `anchor` | `ref` | Required point reference; top-left of the logical rectangle |
| `content` | `text-block` | Required `{kind: "text-block", value: content}` |
| `widthEm` | `number` | Width in selected-font em, 4–120; default 30 |
| `size` | `number` | Text-style size multiplier, 0.5–4; default 1 |
| `align` | `string` | `left`, `center`, `right`; default `left` |

The output slot is `text`, of element type `text`. Invalid dimensions/alignment
produce `invalid_parameter`; invalid content fails structural loading. A missing
or undefined anchor follows the usual reference/upstream rules. No truncation.

## Content

```python
from animageo import native

content = native.normalize_text_block("Условие задачи\nДано: $5 и {0}\n\nРешение")
# {"version": "text-block/v1", "paragraphs": [
#   {"runs": [{"kind": "text", "text": "Условие задачи"}, {"kind": "break"},
#             {"kind": "text", "text": "Дано: $5 и {0}"}]},
#   {"runs": [{"kind": "text", "text": "Решение"}]}]}
assert native.text_block_plain_text(content) == "Условие задачи\nДано: $5 и {0}\n\nРешение"
layout = native.layout_text_block(content, widthEm=12, size=1, align="left",
                                  text_style={"font_size_px": 16})
```

CRLF/CR normalize to LF; tabs become four spaces. A single LF is a `break`;
a pair of LF separates paragraphs. Empty/leading/trailing lines remain. Every
text run is literal: `$`, `\`, `{0}`, `%v` and HTML never execute or interpolate.
There is no formula support in this version. Structured input must have exactly
the canonical shape emitted by normalization; extra fields, noncanonical runs,
embedded LF/CR/tabs, NUL and lone surrogates are rejected.

A block can contain 1–200 paragraphs and 20,000 Unicode code points of
reconstructed text, including LF (two between paragraphs). Run counts are
bounded before joining. All validation errors identify their field and limit.

The renderer counts all blocks in the scene, including hidden blocks, before
allocating geometry. It accepts at most 200 blocks, 32,000 code points and
60,000 glyphs in total. One code point can produce several glyphs. The scene
also has a budget of 8,500,000 Bézier control points, estimated conservatively
at 312 per base glyph and 56 per accent. A scene can reach that budget before
reaching either text limit. Raster previews and video frames allow up to
16,777,216 pixels and 8,192 pixels per side. Exceeding any render budget raises
`ValueError`.

## Deterministic layout

`native.layout_text_block(content, widthEm=30, size=1, align='left', *, text_style=None)`
uses the bundled RusTex T2A `larm1000` font metrics. No manim, TeX process or browser
font measurement is needed. `text_style` accepts only `font_size_px` (default 16,
0.01–10,000); unsupported style keys fail explicitly. This literal-glyph profile
positions font glyphs explicitly and disables automatic TeX ligature substitution.
Latin/extended Cyrillic, typographic quotes, literal ASCII and supported combining accents are measured from
the same font used for drawing. Unsupported glyphs produce an explicit error;
there is no font substitution or estimated layout. Normalization can retain
Unicode outside the drawing font's coverage.

School symbols take glyphs of the other fonts of the same RusTex template
(their metrics are in the same bundled file) and are placed by the TeX
rules of the command each stands for, so a block sets them as a label sets
that TeX:

| Characters | Font, glyph | Set as |
| --- | --- | --- |
| `− · × ∘ ≤ ≥ ≈ ∞ ∈ △ ⊥ ∥` | `cmsy10` | `$-$`, `$\cdot$`, `$\times$`, `$\circ$`, `$\le$`, `$\ge$`, `$\approx$`, `$\infty$`, `$\in$`, `$\bigtriangleup$`, `$\perp$`, `$\parallel$` |
| `≠` | `cmsy10` slash over `cmr10` `=` | `$\neq$` |
| `π` | `cmmi10` | `$\pi$` with its italic correction |
| `∠` | `msam10` angle | the amssymb glyph of `$\angle$` |
| `° ′ ″` | `cmsy7` | `$^\circ$`, `$'$`, `$''$`: raised by `\fontdimen14` of `cmsy10`, plus `\scriptspace` |
| `² ³` | `larm0700` digits | `\textsuperscript{2}`, `\textsuperscript{3}` |
| `…` | three `larm1000` periods | `\textellipsis`: each period followed by `\fontdimen3` |
| `√` | `cmsy10` radical | the radical `\sqrt` puts over a digit, without its bar |

The template's own `\angle` and `\triangle` are scaled composites of fonts
the metrics do not carry; a block uses the single glyphs above. A glyph of
another font has a layout `code` from 256 (`GLYPH_FONTS` in
`animageo/native/text_block.py` names its font and slot); codes below 256 are
`larm1000` slots. Drawing uses the code as the key of the glyph atlas.

A character without a glyph raises `native.UnsupportedGlyphError`, a
`ValueError` with `code = "unsupported_glyph"`, the character `char` and
`index`, the code-point offset of its grapheme in `text_block_plain_text`;
`to_dict()` gives `{code, char, codepoint, index}`.

The greedy algorithm wraps at spaces. Boundary spaces remain on the preceding
line (blank advance may hang past its logical width); long words split at extended grapheme boundaries without inserting hyphens.
A single grapheme exceeding the width fails explicitly. Input/glyph counts bound
time and storage; no unbounded subprocess is part of layout.

The JSON artifact has `format: "animageo-text-block-layout/v1"`, `width`, `height`,
`lines` in reading order, `metricsVersion`, `fontSizePx`, `size`, and `hash`.
Each line has literal `text`, `x`, `baseline`, `width`, and `glyphs` (`code`, `x`,
`y`, optional ink bounds). All geometry is **em of the selected size**; the origin
is top-left, y points down. Glyph positions/ink are relative to the line baseline;
line x/baseline are relative to the block. Baseline spacing is 1.32 em. Alignment
moves each line inside the fixed-width rectangle, preserving the anchor.
Size and font size scale physical dimensions together without changing lines.

`metricsVersion` fingerprints the font metrics, TeX profile and layout profile;
`hash` covers the canonical artifact excluding itself. It is a content identity,
not an authorization token or a cache scope. The caller owns cache isolation.

## Drawing

SVG, PNG, PDF, EPS, TikZ, TeX and video frames consume the same positioned glyphs.
No exporter repeats paragraph wrapping. TikZ/TeX emit positioned nodes directly
from the layout without building Manim objects for blocks. Fully clipped lines
remain in the layout and comments. Vector and video renderers build a fixed
RusTex glyph atlas (the block font and the symbol glyphs) once per process. During anchor motion, each scene reuses the
line contours and changes their world transform. PNG previews draw those paths
onto the image surface directly. Native static/frame reports expose
`elements[id].textBlock = {layout, emToWorld, origin}`; multiply em coordinates by
`emToWorld` and translate by `origin`, the effective world anchor including appearance offsets
(reverse y for world coordinates).
The projection follows the renderer's text-style/source-frame scaling. A failed
block render raises an error rather than exporting an omitted block.

The bridge retains content and parameters during incremental rebuilds. A block
appears or disappears as a unit at its scheduled `at` offset in a timeline.
The transition uses a zero-duration `none` effect in both generated steps and
explicit timelines. `text.free`, captions and labels keep their existing
effects, template, LF and dollar-delimiter semantics.
