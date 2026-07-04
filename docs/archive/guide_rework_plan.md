# Guide rework — structural plan

> Status: **IMPLEMENTED (2026-05-30).** All steps done on branch
> `docs/guide-rework`. The guide is one 12-chapter tree; `docs/style_guide/` and
> `docs/style_guide_new/` are removed; assets/generator live in `docs/guide/`;
> the new §10 web chapter embeds a real live JSXGraph board (verified in headless
> Chrome). Regression guard: `docs/guide/server/validate_examples.py` (26/26).
> Supersedes the 2026-05-04 `docs/archive/guide_audit.md`.
>
> Note vs the original 13-chapter sketch: styles stayed as the existing
> comprehensive §5 (+ targeted illustrations) rather than splitting into two
> chapters — the merge value was assets + the few real illustration gaps + the
> new export/web coverage, not re-prosing already-good chapters. Final count: 12.
>
> **Revision note (this pass):** the goal expanded — (a) **absorb
> `docs/style_guide/` into the one guide** and remove it (and the abandoned
> `docs/style_guide_new/`); (b) make the guide **maximally illustrated** —
> every concept shown visually; (c) freedom to revise the guide's layout /
> approach where it helps. The chapter map and scope below reflect that.

## 0. Method & ground truth

Validated the current guide against the live code before planning, not from memory:

- **All 26 interactive examples render cleanly.** New harness
  `docs/guide/server/validate_examples.py` extracts every `data-example` block
  from `docs/guide/*.html` and renders it through the real `render_example`
  (the same path the live server uses). Result: `26/26 python examples ok, 0 failed`.
- Cross-checked the public surface: `animageo/animageo.py` (6 `export*`
  methods), `animageo/__main__.py` (CLI formats), `style/builtin.json`,
  `style/resolver.py`.

**Conclusion: the guide is not broken — it has drifted in _coverage_.** The
problem the user dislikes is structural: the guide stops at "SVG and MP4" and
predates ~4 shipped subsystems. So this is an *additive restructure + currency
pass*, not a repair job.

### What the old audit got wrong (now stale)

- Claimed §11 still uses legacy keys `size` / `stroke_dash` / `stroke_cap` /
  `right_mark` / `lines`. **Verified false today:** §11 uses the canonical
  `size_px`, `arc_size_px`, `stroke_dash_ratio`, etc. throughout. The reference
  was fixed since. So §11 needs *additions*, not corrections.

## 0a. The style-guide merge (verified facts)

`docs/style_guide/` is **not redundant** with the main guide's §5 — it is a
deeper, separately-structured styling treatment that the main guide already
leans on:

- 8 chapters: architecture, JSON file, `elem.style` keys, labels, ImportPolicy,
  animation+styles, curves, recipes — **plus** a 270-row `reference.html`
  (full builtin-defaults table, `StyleConfig`/`DefaultsProfile`/`StyleOverlay`/
  `ImportPolicy` APIs).
- **56 generated SVG examples** + **4 hand-authored diagrams** (`pipeline.svg`,
  `anchor-grid.svg`, `units.svg`, `zindex.svg`), produced by
  `docs/style_guide/examples/generate_svg.py` (27 example specs).
- The main guide **already serves these assets** via the `/style_guide_assets`
  mount and references them from §5/§6/§10. So the dependency is real today.
- `docs/style_guide_new/` is an **abandoned rebuild** (index + reference only,
  no chapters) → delete.

**Merge approach:** move the assets + generator *into* the guide
(`docs/guide/assets/` + `docs/guide/examples/`), fold the styling depth into
expanded guide chapters (see map), rewire `serve.py` mounts and all cross-links,
then **remove `docs/style_guide/` and `docs/style_guide_new/`**. One guide, one
asset tree, one server.

## 0b. Illustration mandate

Every styling/feature concept gets a visual, not just prose:

- Reuse all 56 existing example SVGs + 4 diagrams (they are current and good).
- Add new generated SVGs for any new styling point that lacks one (via the
  relocated `generate_svg.py` — one source of truth, regenerable).
- Prefer **before/after pairs** and **option grids** (the generator already does
  this for palettes, point sizes, line caps, points-display, polygon fill,
  label anchors, auto-layout, import-policy, z-index).
- Keep interactive (editable) SVG examples where the render server supports them;
  use static SVG/diagram + code where it doesn't (export/web chapters).

## 1. The real gaps (verified)

| Gap | Evidence | Where it should live |
|-----|----------|----------------------|
| **Export covers only SVG + MP4** | guide §9 title is literally "Экспорт SVG и MP4"; 6 export methods exist (`exportSVG/PDF/EPS/TikZ/JSXGraph` + `exportStylePromptSummary`) | rewrite §9 |
| **No TikZ** | `grep tikz docs/guide` → none; `exporters/tikz/`, `docs/tikz_export.md` exist | §9 + reference |
| **No PDF / EPS** | `exportPDF`/`exportEPS` exist; `docs/export_formats.md` covers them | §9 |
| **No GIF / WebM / MOV** | CLI `RENDER_FORMATS=(png,gif,mp4,webm,mov)`; `configure_render` exists | §9 / animation |
| **No interactive web export at all** | `grep jsxgraph docs/guide` → none. This is the flagship recent subsystem: `exportJSXGraph(output="spec")` → `animageo-board/v1`, `web/runtime` (`createBoard`/`BoardHandle`), `<animageo-board>`, adapters | **new chapter** |
| **CLI under-documented** | `animageo` CLI has `--format`, `--keyframes`, `--quality`, `--standalone`, `--dpi`, `--transparent`, logging flags; guide shows only `.ggb → svg` | promote in §9 + a CLI box |
| **AI / summary pipeline absent** | `exportStylePromptSummary`, `docs/construction_summary.md`, `docs/ai_*` | reference + a short §recipes note |
| **Reference missing new surface** | §11 has no `exportPDF/EPS/TikZ/JSXGraph`, no `JSXGraphOptions`/`TikZOptions`, no `animageo-board/v1` keys | extend §11 |

## 2. Proposed chapter map (merged guide)

Keep the 1–8 spine (verified correct and well-paced) but **deepen the styling
chapters** by folding in the style-guide material, rework the export tail, and
add the web chapter. New section grouping for clarity in the nav:

> **Основы**: 1–4 · **Стили и подписи**: 5–7 · **Кривые и анимация**: 8–9 ·
> **Вывод**: 10–11 · **Справочник**: 12–13

| # | Chapter | Change | Source / why |
|---|---------|--------|--------------|
| 1 | Что такое AnimaGeo | **light edit** | Add an "outputs" map (static vector / render / interactive web) so breadth shows from page one. More illustration in the hero. |
| 2 | Установка и первый запуск | **light edit** | Note optional web-runtime deps; keep CLI teaser. |
| 3 | Python-DSL | **keep** (+illustrate) | Current; add a couple of element-gallery SVGs. |
| 4 | Загрузка из GeoGebra | **merge-in** | Fold style-guide §5 (ImportPolicy depth: priorities, mini-DSL, `pointStyle`→3 axes, `reloadPolicy`, embedding) into the existing §4. Keep its import-policy SVGs (mixed-vs-unified). |
| 5 | **Стили: архитектура и слои** | **rewrite/expand** | Merge guide §5 + style-guide §1 (resolver chain, `StyleConfig.load`, overlay-without-materialisation, preset refs, pixel-invariance, type names). Use `pipeline.svg`, `units.svg` diagrams. |
| 6 | **Стили: JSON-файл и elem.style** | **new (from merge)** | style-guide §2 (full JSON skeleton, presets, defaults, overlay/per_type/per_name, angle_radius, label_placement) + §3 (every `elem.style` key, grouped: stroke/fill/points/angles/ticks/fonts). Heavily illustrated: palettes, point sizes/shapes, line widths/caps/dashes, polygon fill, multi-arc, right-angle marker, tick marks. |
| 7 | **Подписи и автораскладка** | **merge/expand** | guide §6 + style-guide §4 (greedy solver, per-type strategy, angle effective radius + two gaps, 3 modes, API, dynamic tracker). Diagrams: `anchor-grid.svg`; before/after auto-layout SVGs. |
| 8 | Кривые | **merge/keep** | guide §7 + style-guide §7 render details (adaptive sampler, viewport clipping, marching squares, asymptotes, curve fill). Keep all curve SVGs. |
| 9 | Анимации | **light edit** | guide §8 + style-guide §6 style-in-animation bits (animating style props, label snapshots); add GIF/WebM/MOV via `configure_render`; cross-link §11. |
| 10 | **Экспорт: все форматы** (was §9) | **rewrite** | Two static tracks (SVG/PDF/EPS/TikZ) + render track (PNG/GIF/MP4/WebM/MOV), picker table from `docs/export_formats.md`, px_size/ptUnit/Retina (kept), CLI `-o`/`--format`/`--dpi`/`--standalone`. Illustrated with a "same scene, N formats" panel. |
| 11 | **Интерактивный веб-экспорт** (NEW) | **new** | Flagship. `exportJSXGraph` live vs static; `output="spec"` + `animageo-board/v1`; `web/` layer — `createBoard`→`BoardHandle` (signals/actions), `<animageo-board>`, adapters; coverage report; decorations. Embeds a real live board (CDN JSXGraph, client-side) + a screenshot fallback. |
| 12 | Рецепты | **merge** | guide §10 + style-guide §8 recipes (dedup). Add "GGB→widget", "one figure in N formats". |
| 13 | Справочник | **merge/extend** | guide §11 + style-guide `reference.html` (the 270-row builtin-defaults table, `StyleConfig`/`DefaultsProfile`/`StyleOverlay`/`ImportPolicy` APIs) + new surface: `exportPDF/EPS/TikZ/JSXGraph`, `TikZOptions`/`JSXGraphOptions`, `animageo-board/v1` fields, CLI flag table. |

Net vs today (guide 11 ch + style_guide 8 ch + reference): **one guide of 13
chapters**; styling depth preserved and better integrated; **2 directories
removed**; +1 export rewrite; +1 new web chapter; all assets relocated in.

## 3. Examples to add (each validated via the harness before commit)

The interactive render server only does **static SVG** (it's the SVG pipeline).
So new interactive (editable) examples must stay SVG-renderable. The new
export/web material is shown as **code + a pre-rendered artifact**, not as a
live editable block — honest about what the in-browser server can do.

| Chapter | New example | Kind |
|---------|-------------|------|
| 9 | same scene → `exportSVG` / `exportPDF` / `exportTikZ` (code, with a rendered SVG preview) | code + SVG |
| 9 | CLI one-liners for each format | bash (static) |
| 10 | `exportJSXGraph("board.html")` + the `output="spec"` JSON shape | code + JSON |
| 10 | `createBoard(spec, el).on('change', …)` minimal embed | js (static) |
| 10 | `<animageo-board spec="…">` snippet | html (static) |
| 11 | "GGB → interactive widget" recipe | code |

Existing 26 examples stay; the harness keeps them honest.

## 4. Infrastructure changes

- **Asset migration**: move `docs/style_guide/examples/` (incl.
  `generate_svg.py`, `anim_scenes.py`, `guide_style.json`) → `docs/guide/examples/`,
  and `docs/style_guide/assets/` (56 example SVGs + 4 diagrams) →
  `docs/guide/assets/`. Update `generate_svg.py` output paths. One regenerable
  source of truth, living with the guide.
- **serve.py rewrite (mounts)**: drop the `/style_guide`, `/style_guide_new`,
  `/style_guide_assets` mounts; serve `docs/guide/assets/` directly. `runner.py`
  imports `generate_svg` from the new in-guide path. The startup banner stops
  advertising the separate guides.
- **Cross-links**: every guide chapter currently linking to `../style_guide/...`
  or `style_guide_assets/...` is rewritten to in-guide paths. (10 chapters +
  index + README reference it — see grep in §0a.)
- **Remove** `docs/style_guide/` and `docs/style_guide_new/` once content +
  assets are absorbed and links are clean.
- **Regression guard**: keep `validate_examples.py`; extend it to also render
  every `generate_svg.py` example (so the static asset set is validated too).
  Wire a one-line invocation into the guide README.
- **Navigation**: 13-entry nav with section groups (Основы / Стили и подписи /
  Кривые и анимация / Вывод / Справочник); `index.html` cards rebuilt.
- **New assets**: regenerate any added styling SVGs via `generate_svg.py`; a
  live JSXGraph board (client-side CDN) + a committed screenshot fallback for §11.
- **CSS**: guide's `css/style.css` (1133 lines) is already the superset; port any
  style-guide-only rules (diagram/figure framing) so merged pages look uniform.

## 5. Out of scope (explicit)

- No Pyodide / client-side Python for the SVG examples (infeasible — README).
- No live *interactive-geometry* editing inside the SVG examples (the server
  renders frames; the JSXGraph board is the interactive path, shown in §11).
- `docs/*.md` design docs (api.md, styles.md, architecture.md, etc.) stay as-is
  here — this task is the **HTML guide**; the .md currency pass is the separate
  earlier task item (export_formats.md etc. already updated).

## 6. Execution order (after approval)

1. **Asset migration + serve.py mounts** (move examples/assets into guide; fix
   `runner.py`/`generate_svg.py` paths; rewrite mounts) — verify server still
   renders + `validate_examples.py` green.
2. **§13 Справочник** merge/extend (lowest risk, additive) + harness.
3. **§5/§6/§7** styling deepen (absorb style-guide §1–4) + relocate diagrams +
   harness after each.
4. **§8/§9** curves+animation merge (style-guide §6–7) + harness.
5. **§10 rewrite** (all export formats) + new SVG panel + harness.
6. **§11 new chapter** (interactive web) + live board + screenshot.
7. **§4 merge** (ImportPolicy depth) + **§1/§2/§3 light edits**.
8. **Nav/index** rebuild (13 ch, section groups) across all chapters; rewrite all
   cross-links to in-guide paths.
9. **Remove** `docs/style_guide/`, `docs/style_guide_new/`.
10. Full `validate_examples.py` pass + spot-open every chapter in the server +
    visual check of merged pages.
