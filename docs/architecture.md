# Architecture

Related documents:

- `docs/styles.md` — the main style reference and layer-responsibility guide.
- `docs/import_policies.md` — details of GGB import/adaptation and `ImportPolicy`.
- `docs/field_names.md` — table of GGB XML → `ggb_raw` → `ggb_style` / `elem.style` → JSON/render.
- `docs/guide/index.html` — interactive HTML guide, in Russian (styling topics in §5–§7, reference in §11). It must be served from a local web server — it does not render on GitHub.

## Processing pipeline

```
 .ggb file (ZIP with XML)                  Python DSL code (string / .py)
       |                                          |
       v                                          v
 ┌─────────────┐                         ┌────────────────┐
 │ ggb_parser  │────┐                    │ parsers/dsl/   │
 └─────────────┘    │                    │ (exec engine)  │
                    │                    └────────┬───────┘
                    v                             v
 ┌──────────────────────────────────────────────────────┐
 │ Construction                                         │
 │   elements[]   (+ ggb_raw + ggb_style)               │
 │   vars[]                                             │
 │   commands[]                                         │
 │   state{}                                            │
 └──────┬───────────────────────────────────────────────┘
        |
        v
 ┌────────────────────────────────────────┐
 │ applyStyle                             │
 │   + GeoStyle     (scene export ctx)    │
 │   + StyleConfig  (builtin.json +       │
 │                    user JSON, merged)  │
 │   + ImportPolicy (GGB raw → ggb_style) │
 └──────┬─────────────────────────────────┘
        |
        v                  addAllGeometry:
 ┌──────────────┐
 │ CreateMObject│◄─── reads via resolver.resolve:
 │   ──> mobject│          │   elem.style → per_name → per_type →
 └──────┬───────┘          │   ggb_style → defaults
        |                  v
        |
┌───────┴───────┐
v               v
┌───────────┐  ┌───────────┐
│ svg_parser│  │   manim   │
│  (Cairo)  │  │ renderer  │
└─────┬─────┘  └─────┬─────┘
      v              v
   .svg           .mp4
```

The parser records raw GGB values in `elem.ggb_raw` (`point_size`, `point_style`, `line_thickness`, `line_type`, `line_opacity`, `arc_size`, `label_offset_px`, `obj_color`, plus label/visibility flags such as `label_mode`, `label_caption`, `show_object`, `show_label`). `obj_color` stores the original `r/g/b/alpha` along with convenient `hex` / `opacity` aliases. Normalized visual keys go into `elem.ggb_style`; `ImportPolicy` decides how the raw values are further adapted — "as in GGB", a fixed value, a callable, quantization, or a remap. The resolver includes this layer only when `import.enabled != false`.

### Style subsystem: three layers

```
Read priority (resolver.resolve(scene, elem, key)):

 1. elem.style[key]              ← explicit writes (DSL/API)
 2. overlay.per_name[name][key]  ← targeted override for one element
 3. overlay.per_type[type][key]  ← override for all elements of a type
 4. elem.ggb_style[key]          ← GGB import/adaptation, when enabled
 5. defaults.by_type[type][key]  ← per-type baseline (builtin.json + user JSON)
 6. non-explicit elem.style[key] ← intrinsic fallback seeded by geometry classes
 7. caller-supplied default=     ← hard fallback
```

Each layer has a single responsibility:

- **`DefaultsProfile`** — package-shipped `builtin.json` + user JSON (deep merge). Per-type baseline in **pixels** (`size_px`, `stroke_width_px`, `arc_size_px`, …). Never writes into `elem.style`.
- **`StyleOverlay`** — `per_type` / `per_name` + automation (`angle_radius`, `label_placement`). Logically sits above GGB import and defaults; the resolver reads the overlay directly from `StyleConfig`.
- **`GGBImportPolicy`** (i.e. `ImportPolicy`) — GGB transforms only: `scale:/quantize:/remap:` over `elem.ggb_raw`, with the result stored in `elem.ggb_style`. DSL elements are skipped (their raw layer is empty).

Unit contract: every `*_px` key in `elem.style`, `elem.ggb_style`, and `defaults.<type>` is in **pixels**. The renderer divides by `ptUnit` at draw time. The legacy `GeoStyle.ang_rdefault / ang_rshift / ang_right / dot_size` fields are pixel-valued as well.

## Modules

| Module | Role |
|--------|------|
| `animageo.py` | Scene, animations, `CreateMObject` (dispatcher + per-type `_render_<type>` renderers + `_build_render_ctx` + `_renderer_for` + `_make_label`), `loadGGB`, ImportPolicy wiring |
| `__main__.py` | CLI entry point (`python -m animageo file.ggb -o out.svg`): static vector track (svg/pdf/eps/tikz) and manim render track (png/gif/mp4/webm/mov, `--keyframes` for animation) |
| `ui.py` | TeX templates, `create_label` (9-point anchors), `ValueLabel` (DecimalNumber-backed fast value labels) + `prewarm_decimal_glyphs`, `install_cyrillic_tex_template`, NumberedFrame, CustomArrowTip |
| `labels.py` | Final label-text resolution: `resolve_label_text`, `resolve_label_spec` (structured `LabelSpec` for the fast value-label path), label modes (name/value/name+value) |
| `constants.py` | Z-index tiers (Z_FILL, Z_LINE, Z_POINT, Z_LABEL) and scaling coefficients |
| `keyframes.py` | Keyframe animation: JSON parsing, interpolators, easing, `LabelOffsetInterpolator` + `attach_label_layouts` |
| `label_placement.py` | Auto label placement: greedy solver + 8 candidates, `compute_label_layout` (pure), `apply_label_layout` (impure), `compute_angle_label_center`, `compute_effective_arc_size_px` (angle_radius), bbox LRU cache, EMA+hysteresis helpers |
| `export_layout.py` | Export canvas layout: `ExportLayout`, `compute_export_layout`, size/fit/anchor/padding normalization for export options |
| `render_config.py` | `configure_render` (output format / fps / transparency) + GIF palette fix |
| `logging_config.py` | `configure_logging` helper backing the CLI `--verbose` / `--quiet` / `--log-level` flags |
| `style/__init__.py` | `GeoStyle` (scene-level container: palette, export params, render flags), color utilities, re-export of constants/scaling |
| `style/config.py` | `StyleConfig` (top level), `DefaultsProfile`, `StyleOverlay`, `deep_merge` for multi-file JSON merging; `resolve_style_input` (maps a bare preset name to the packaged preset JSON path; paths/dicts pass through) + `available_style_presets` |
| `style/presets/*.json` | Packaged style presets (`default`, `book_blue`, `book_green`, `book_purple`, `book_red`), selectable by name via `resolve_style_input` |
| `style/resolver.py` | `resolve(scene, elem, key)` + `resolved_style(scene, elem)` + `trace(…)` for debugging the chain |
| `style/builtin.json` | Package-shipped per-type defaults in pixels; always loaded, user JSON merges on top |
| `style/schema.py` | Documentation and validation of JSON styles + `import_policy` sections (+ `overlay` in NEW_TOP_KEYS) |
| `style/scaling.py` | Named conversion functions: GGB px ↔ JSON style ↔ internal units |
| `style/import_policy.py` | `ImportPolicy` dataclass — GGB-only transforms (`scale:`, `quantize:`, `remap:`) |
| `style/dsl.py` | Mini-DSL for JSON values: `const:`, `scale:`, `quantize:`, `remap:` |
| `style/ggb_resolver.py` | `resolve_ggb_style(ggb_raw)` — reproduces the GGB import-style layer for faithful mode |
| `style/animatable.py` | Registry of animatable `elem.style` keys for keyframes v2 style tracks (interpolation kind per key; manim-free) |
| `style/colorspace.py` | sRGB ↔ Oklab conversion and color interpolation for keyframe style tracks (manim-free) |
| `style/enums.py` | Style vocabularies (`Literal` aliases + runtime tuples) and the GGB `pointStyle` → shape/fill/stroke decomposition table |
| `style/proxy.py` + `proxy.pyi` | `StyleProxy` — dict subclass with attribute-style access to `elem.style` and explicit-write tracking |
| `geo/construction.py` | Dependency graph, topological sort (Kahn), rebuild, apply, `update_tparam`, `rename`, `add_and_build` |
| `geo/lib_elements.py` | Point, Line, Segment, Ray, Angle, Polygon, Circle, Arc, CircleSector, Vector, LocusCurve, Text (+ re-export of Conic/Function/ImplicitCurve); human-readable fields (`.coords`, `.center/.radius`, `.normal/.offset/.direction`, `.vertex/.size/.side1/.side2`, `.endpoints`, `.vertices`, …); `Element.__getattr__` forwards to `.data` |
| `geo/lib_conic.py` | `Conic` (3×3 matrix `.matrix`), invariant-based classification, `as_ellipse/as_parabola/as_hyperbola/as_lines/as_point`, `Conic.from_string(equation)` |
| `geo/lib_function.py` | `Function` — explicit `y = f(x)` (`.expr`, `.var`, `.source`), sympy parsing, `If[...]` → `Piecewise`, chained `a ≤ x ≤ b`, `natural_singularities`, lambdify |
| `geo/lib_implicit.py` | `ImplicitCurve` — arbitrary `F(x, y) = 0` (`.expr`, `.var_x/.var_y`, `.source`), sympy parsing, two-argument lambdify |
| `geo/curve_sampling.py` | Viewport-aware adaptive sampler + Liang–Barsky clipping; analytic t-ranges for parabola/hyperbola; marching squares for implicit curves |
| `geo/lib_commands.py` | Geometric operations (400+ dispatchable entries in `COMMAND_REGISTRY`): intersections for all pairs (including numeric F/I), Conic commands (Center/Focus/Vertex/Axes/Directrix/Polar/Tangent), Ellipse/Hyperbola/Parabola constructors, `function_T/conic_T/implicit_curve_T` for the string DSL |
| `geo/lib_vars.py` | `Measure(value, dimension)`, `AngleSize`, `Boolean(value)` |
| `geo/tparam.py` | Point ↔ curve-parameter (tparam) math for every path type; backend of `Construction.tparam_from_coords` and the keyframe system |
| `geo/utils.py` | is_number, is_angle_degrees, is_boolean |
| `parsers/ggb_parser.py` | XML extraction from .ggb, construction parsing, `ggb_raw` population; `<expression type="conic/line/function/implicitpoly">` with an `=` sign; expressions are routed through `dsl.run` internally |
| `parsers/ggb_macro.py` | Custom-tool macro expansion: parses `geogebra_macro.xml` definitions and inlines macro calls into primitive commands before parsing (recursive expansion supported) |
| `parsers/ggb_generator.py` | Generates .ggb archives from a Construction (GeoGebra XML serialisation + ZIP packaging) |
| `parsers/dsl/` | Python DSL (exec engine): `transform.py` (AST rewriter, loop scoping, name shaping, forbid list), `registrar.py` (`__reg__`/`__reg_loop__`/`__reg_tuple__` + ContextVar), `namespace.py` (FactoryDict with `__missing__` for 99 auto-discovered command factories backed by 433 dispatch signatures + math + `style/hide/show` helpers + forward refs for `addVar` variables), `proxy.py` (ElementProxy with `__getattr__` into data plus `+/-/*//`/`abs` arithmetic), `sugar.py` (`f(x) = expr` pre-pass), `stub_gen.py` (`<scene>_stubs.pyi` after `loadGGB`). Entry points: `dsl.run(constr, code)`, `with dsl.scope(c):`, `scene.putCode(code)`, `scene.loadCode(path)`. Stubs: `namespace.pyi`, `proxy.pyi`. |
| `dsl.py` + `dsl.pyi` | Super-module — `from animageo.dsl import *` gives all factories and types in the IDE |
| `parsers/svg_parser.py` | Cairo rendering of manim objects to SVG |
| `exporters/tikz/` | Semantic TikZ export (`scene.exportTikZ`): walks drawable elements in z-order and emits native TikZ through the same style resolver as the renderer |
| `exporters/jsxgraph/` | Interactive JSXGraph export (`scene.exportJSXGraph`): transpiles the construction graph into live `board.create` calls; outputs html/js/spec/json/moodle |
| `exporters/construction_summary.py` | Compact JSON construction summary for AI style generation (`construction_to_ai_summary`, `write_ai_summary`) |

## Dependency system

Every element of a construction has a **level**:

- **Level 0** --- free points defined by coordinates
- **Level N** --- elements depending on elements of level N-1

```
Level 0:  A(0,0)   B(4,0)   C(0,3)
Level 1:  M = Midpoint(A, B)       s = Segment(A, B)
Level 2:  h = Segment(C, M)
```

When an element changes, only its dependents are rebuilt (lazy rebuild).

## Label placement

`label_placement.py` operates in three modes:

**1. Static one-shot** (`auto_place_labels(scene)` / `scene.autoPlaceLabels()`):
- `compute_label_layout` (pure) collects `LabelInfo` for all visible labels, gathers obstacles (segments, circles, point cloud), picks a preferred direction for each label, and runs a priority-ordered greedy solver over 8 candidates.
- Returns `dict[name, LabelPlacement]` without mutations.
- `apply_label_layout` (impure) writes the result into `elem.style['label_offset_px']` / `elem.style['label_anchor']` and re-renders the scene.
- The Tex bbox is cached by `(text, font_size)` — keyframe snapshots and per-frame recomputation reuse the measurements.

**2. `play_keyframes` + `keyframe_snapshots=true`**:
- Pre-pass: save `get_independents()` + visibility, walk all keyframes (carry-forward values), call `compute_label_layout` at each one, collect snapshots `list[dict[name, LabelPlacement]]`. Restore the state, run `rebuild(full=True)`.
- Before actual playback, `_apply_keyframe_state(seq.keyframes[0], seq.element_info)` is called: the first keyframe's values and `show`/`hide` are written into the construction, `geo.rebuild()` runs, then `updateGeoElements()` refreshes the affected mobjects. This makes the first rendered frame independent of the saved `.ggb` state.
- `KeyframeSequence.attach_label_layouts(layouts)` binds the snapshots to intervals: for `kind='static'` labels it creates a `LabelOffsetInterpolator` (linear or smooth interpolation of the ggb offset between snapshots); for `kind='dynamic_angle'` — `AngleParams`, so the bisector is recomputed per frame.
- In `_play_keyframe_interval.on_frame` the label pass runs AFTER `geo.rebuild()` (so `ang.side1/.side2/.vertex` are fresh) and BEFORE `updateGeoElements()` — labels render in the same `mob.become(CreateMObject(elem))` as the geometry.

**3. `autoPlaceLabels(dynamic=True)` under `addUpdater`**:
- Installs a `LabelTracker` (a dict on the scene with `prev_offset`, `prev_anchor`, `anchor_flip_counter`, `angle_params`, `cfg`).
- `updateVar` after `geo.rebuild()` + `updateGeoElements()` calls `_apply_dynamic_labels`:
  - for dynamic-angle labels — `compute_angle_label_center` without smoothing (the function is continuous by itself);
  - for static labels — EMA (`apply_ema_step`) on the offset + Schmitt trigger on the anchor (`anchor_hysteresis_step`);
  - throttling via `solver_every_n_frames`.

MC canonicalization (`canonicalize_anchor=true`) rewrites every label from `(anchor=A, offset=O_A)` to `(anchor='MC', offset=O_A - edge_A·halfExtent·ptUnit_ggb)`. The visual center is preserved, but the anchor is always the same → interpolation produces no discrete jumps when the direction changes between keyframes. Off by default so existing snapshot tests keep passing.

**Angle geometry taken into account by the layout:**

- **Multi-arc:** angle labels move past the outermost arc when `elem.style['tick_count'] > 1` — effective radius = `arc_size_px + (lines − 1) · ang_rshift`, the same formula used by both the renderer and the layout.
- **Two independent gaps:** `angle_gap_arc_px` (arc → label) and `angle_gap_sides_px` (angle sides → label bbox for narrow angles). The removed unified `angle_gap_px` key is no longer read.
- **Automatic arc-radius scaling (`overlay.angle_radius`, default off):** `compute_effective_arc_size_px` is shared by the renderer (`animageo.py:CreateMObject`) and the layout (`compute_label_layout` + `_collect_labels`). Formula `base · (pivot_rad / angle) ** exp`, clamped to `[min_px, max_arm_fraction · min_arm_px]`. The label automatically follows the scaled arc because the number comes from a single source. Per-element escape: `elem.style['auto_radius'] = False`. The renderer takes `arc_size_px` through the resolver; DSL angles without an explicit `elem.style['arc_size_px']` use the pixel path via the builtin default (17 px).

## Command dispatch

Functions in `lib_commands.py` are named by the pattern:

```
{command_name}_{argument_types}
```

Type shortcuts:

| Letter | Type |
|--------|------|
| `p` | Point |
| `l` | Line |
| `s` | Segment |
| `r` | Ray |
| `c` | Circle |
| `C` | Arc |
| `S` | CircleSector |
| `a` | Angle |
| `v` | Vector |
| `P` | Polygon |
| `i` | int / float |
| `m` | Measure |
| `A` | AngleSize |
| `b` | Boolean |
| `K` | Conic |
| `F` | Function |
| `I` | ImplicitCurve |
| `T` | str (DSL literal for string-arg constructors) |

Examples: `midpoint_pp`, `intersect_lc`, `rotate_pAp`, `distance_pp`,
`intersect_KK` (conic ∩ conic via the pencil method), `intersect_Kl` (conic ∩ line),
`intersect_FK` (function ∩ conic via substitution), `intersect_II`
(implicit ∩ implicit via marching squares + Newton), `center_K`,
`focus_K`, `polar_pK`, `tangent_pK`, `ellipse_ppi`, `parabola_pl`,
`conic_ppppp` (conic through 5 points), `function_T` (Function("y = x²")).

The dispatcher (`Command.func()`) looks the name up in `COMMAND_REGISTRY`, populated from the module's functions at import time.

## Higher-order curves: Conic, Function, ImplicitCurve

Three classes covering everything that does not reduce to a line/circle/polygon:

```
┌───────────────────────────────────────────────────────────────────┐
│ Conic (lib_conic.py)                                              │
│   matrix ∈ ℝ³ˣ³ symmetric  — (x, y, 1)·matrix·(x, y, 1)ᵀ = 0      │
│   Lazy classification by the invariants det(matrix),              │
│   det(matrix₃₃), rank → 9 subtypes (circle / ellipse / parabola / │
│   hyperbola / intersecting_lines / parallel_lines / double_line / │
│   point / empty). Canonical parametrization via                   │
│   eigendecomposition of matrix₃₃; degenerate cases decomposed     │
│   through (±λ) eigenvectors.                                      │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ Function (lib_function.py)                                        │
│   sympy.Expr + free variable; lambdify('numpy') exactly once.     │
│   GGB → sympy preprocessor: `^ → **`, `≤/≥ → <=/>=`,              │
│   chains `a ≤ x ≤ b → (a ≤ x) & (x ≤ b)`,                         │
│   `If[cond, then [, else]] → Piecewise((then, cond), …)`.         │
│   `natural_singularities` via `sympy.singularities`.              │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ ImplicitCurve (lib_implicit.py)                                   │
│   F(x, y) = 0 of arbitrary form (polynomial or not).              │
│   `LHS = RHS` is normalized to `(LHS) − (RHS) = 0`.               │
│   Two-argument lambdify; NaN-safe evaluation.                     │
└───────────────────────────────────────────────────────────────────┘
```

## Curve rendering and viewport clipping

All three types render through one shared layer in `curve_sampling.py`:

- **`sample_parametric(func, t_range, viewport, ...)`** — adaptive
  sampler. Starts from a uniform 32-point grid; where the step in scene MU
  exceeds `segment_mu` (default `3 / ptUnit`, i.e. 3 pixels), it inserts
  midpoints into long segments. A **hard cap** of `max_samples=500`
  per mobject guarantees no hangs on pathological expressions. Viewport
  clipping via **Liang–Barsky**, breaking the polyline when it leaves
  the frame.
- **`viewport_t_ranges_parabola(...)` / `viewport_t_range_hyperbola_branch(...)`** —
  analytically narrow the t-range to the viewport intersection in the conic's
  canonical frame. Parabola: `|u| ≤ 2·√(p·v_max)` (with `v_min > 0` — two
  ranges). Hyperbola (per branch): `|t| ≤ min(acosh(u_max/a), asinh(v_max/b))`.
- **`marching_squares(F, viewport, grid_n=128)`** — the classic 16-case
  algorithm for `ImplicitCurve`. O(grid_n²) work, constant memory — no
  hangs. Linear interpolation of zeros on cell edges.

`CreateMObject` branches:

| Type | Strategy | Notes |
|------|----------|-------|
| `Conic (circle)` | `manim.Circle` with direct parameters | closed contour, fill works |
| `Conic (ellipse)` | `manim.Ellipse` + `.rotate().move_to(...)` | closed contour, fill works |
| `Conic (parabola)` | `make_parabola_param` + `viewport_t_ranges_parabola` + `sample_parametric` | one or two polylines |
| `Conic (hyperbola)` | `make_hyperbola_branch_param` × 2 branches | each branch is a polyline |
| `Conic (intersecting/parallel/double lines)` | `as_lines()` → `Line.get_endpoints(corners)` | reuses the existing line renderer |
| `Conic (point)` | `manim.Dot` | — |
| `Conic (empty)` | `None` | nothing is drawn |
| `Function` | `(t, f(t))` as parametric + splitting at `natural_singularities` + `sample_parametric` | `y = 1/x` gives two polylines, `tan(x)` — several pieces between discontinuities |
| `ImplicitCurve` | `marching_squares` → list of segments, each a `manim.Line` | lemniscates, "hearts", trigonometric patterns |

## Intersections

All nontrivial pairs are implemented:

| Pair | Method | Function |
|------|--------|----------|
| Conic ∩ Line | Substitute the line parametrization into `pᵀMp = 0` → quadratic | `intersect_Kl` |
| Conic ∩ Conic | Pencil: `det(λM₁ + M₂) = 0` → cubic → decompose λ·M₁+M₂ into a pair of lines → `intersect_Kl` | `intersect_KK` |
| Conic ∩ Circle | Circle → Conic adapter + `intersect_KK` | `intersect_Kc` |
| Conic ∩ Arc/Segment/Ray | `intersect_Kl` + membership filter | `intersect_KC`/`Ks`/`Kr` |
| Function ∩ Line | Substitute `y = f(x)` into the line equation → `sympy.solve` first, then a sign-change scan with bisection fallback | `intersect_Fl` |
| Function ∩ Conic | Substitution → 1D: `pᵀ·M·p` with `p = (x, f(x), 1)` | `intersect_FK` |
| Function ∩ Circle | `_circle_to_conic` + FK | `intersect_Fc` |
| Function ∩ Function | `f₁(x) − f₂(x) = 0` | `intersect_FF` |
| ImplicitCurve ∩ Line/Segment/Ray | Substitute the line parametrization into F → 1D | `intersect_Il/Is/Ir` |
| ImplicitCurve ∩ Conic/Circle/Function | Marching squares of F₁ → root-find F₂ along each segment → Newton refinement via `scipy.fsolve` | `intersect_IK/Ic/IF` |
| ImplicitCurve ∩ ImplicitCurve | Same approach | `intersect_II` |

All functions have `*i` index variants for `Intersect[..., n]` and
reversed-argument variants (`_Kl`/`_lK`).
