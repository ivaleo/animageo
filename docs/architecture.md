# Архитектура

Смежные документы:

- `docs/styles.md` — главный справочник по стилям и ответственности слоёв.
- `docs/import_policies.md` — детали GGB import/adaptation и `ImportPolicy`.
- `docs/field_names.md` — таблица GGB XML → `ggb_raw` → `ggb_style` / `elem.style` → JSON/render.
- `docs/guide/index.html` — интерактивный HTML-гайд (стили в §5–§7, reference в §12).

## Конвейер обработки

```
 .ggb файл (ZIP с XML)                     Python-DSL код (строка / .py)
       |                                          |
       v                                          v
 ┌─────────────┐                         ┌────────────────┐
 │ ggb_parser  │────┐                    │ parsers/dsl/   │
 └─────────────┘    │                    │ (exec-engine)  │
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
 │   + StyleConfig  (new: builtin.json +  │
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

Парсер записывает в `elem.ggb_raw` сырые GGB-значения (`point_size`, `line_thickness`, `line_opacity`, `line_type`, `arc_size`, `label_offset_px`, `obj_color`, `fontPx`). `obj_color` хранит исходные `r/g/b/alpha` и удобные алиасы `hex` / `opacity`. Нормализованные visual keys складываются в `elem.ggb_style`; `ImportPolicy` решает, как raw-значения дополнительно адаптировать — «как в GGB», «фиксированное значение», callable, квантизация или remap. Resolver включает этот слой только при `import.enabled != false`.

### Стилевая подсистема: три слоя

```
Приоритет чтения (resolver.resolve(scene, elem, key)):

 1. elem.style[key]              ← явные записи (DSL/API)
 2. overlay.per_name[name][key]  ← точечный оверрайд
 3. overlay.per_type[type][key]  ← оверрайд всех элементов типа
 4. elem.ggb_style[key]          ← GGB import/adaptation, если включён
 5. defaults.by_type[type][key]  ← per-type baseline (builtin.json + user JSON)
 6. intrinsic geometry style     ← fallback классов геометрии
 7. default= от вызывающего      ← hard fallback
```

Каждый слой имеет единственную ответственность:

- **`DefaultsProfile`** — package-shipped `builtin.json` + user JSON (deep-merge). Per-type baseline в **пикселях** (`size_px`, `stroke_width_px`, `arc_size_px`, …). Никогда не пишет в `elem.style`.
- **`StyleOverlay`** — `per_type` / `per_name` + автоматика (`angle_radius`, `label_placement`). Логически находится поверх GGB import и defaults; resolver читает overlay напрямую из `StyleConfig`.
- **`GGBImportPolicy`** (тот самый `ImportPolicy`) — только GGB-трансформации: `scale:/quantize:/remap:` над `elem.ggb_raw`, результат в `elem.ggb_style`. DSL-элементы пропускаются (их raw пуст).

Юнит-контракт: каждый `*_px` ключ в `elem.style`, `elem.ggb_style` и `defaults.<type>` — **пиксели**. Рендерер делит на `ptUnit` при отрисовке. Ранее `GeoStyle.ang_rdefault / ang_rshift / ang_right / dot_size` проходили через `json_size_to_internal` × 0.02 и коллапсировали в доли пикселя для DSL-сцен — исправлено.

## Модули

| Модуль | Назначение | Строк |
|--------|-----------|-------|
| `animageo.py` | Сцена, анимации, `CreateMObject` (диспетчер + 13 `_render_<type>` + `_build_render_ctx` + `_renderer_for` + `_make_label`), `loadGGB`, ImportPolicy wiring | ~1820 |
| `ui.py` | TeX-шаблон, labels, NumberedFrame, CustomArrowTip | ~350 |
| `constants.py` | Z-index тиры (Z_FILL, Z_LINE, Z_POINT, Z_LABEL) и scaling-коэффициенты | ~25 |
| `keyframes.py` | Keyframe-анимация: парсинг JSON, интерполяторы, easing, `LabelOffsetInterpolator` + `attach_label_layouts` | ~410 |
| `label_placement.py` | Авто-раскладка: greedy + 8 кандидатов, `compute_label_layout` (pure), `apply_label_layout` (impure), `compute_angle_label_center`, `compute_effective_arc_size_px` (angle_radius), bbox LRU, EMA+hysteresis helpers | ~810 |
| `_stubs.py` | Type stubs для IDE-автодополнения (не импортируется в runtime) | ~610 |
| `style/__init__.py` | `GeoStyle` (scene-level контейнер: палитра, export params, render flags), цветовые утилиты, re-export констант/скейлинга | ~275 |
| `style/config.py` | **Новый.** `StyleConfig` (top-level), `DefaultsProfile`, `StyleOverlay`, `deep_merge` для multi-file JSON-слияния | ~220 |
| `style/resolver.py` | **Новый.** `resolve(scene, elem, key)` + `resolved_style(scene, elem)` + `trace(…)` для дебага цепочки | ~130 |
| `style/builtin.json` | **Новый.** Package-shipped дефолты в пикселях per-type; загружается всегда, user JSON сливается сверху | — |
| `style/schema.py` | Документация и валидация JSON-стилей + `import_policy`-секции (+ `overlay` в NEW_TOP_KEYS) | ~130 |
| `style/scaling.py` | Именованные функции: GGB px ↔ JSON style ↔ internal units | ~115 |
| `style/import_policy.py` | Dataclass `ImportPolicy` — GGB-only трансформации (`scale:`, `quantize:`, `remap:`) | ~235 |
| `style/dsl.py` | Мини-DSL для JSON: `const:`, `scale:`, `quantize:`, `remap:` | ~100 |
| `style/ggb_resolver.py` | `resolve_ggb_style(ggb_raw)` — воспроизводит GGB import-style слой для faithful-режима | ~100 |
| `geo/construction.py` | Граф зависимостей, топологическая сортировка (Кан), rebuild, apply, `update_tparam`, `rename`, `add_and_build` | ~540 |
| `geo/lib_elements.py` | Point, Line, Segment, Ray, Angle, Polygon, Circle, Arc, Vector (+ re-export Conic/Function/ImplicitCurve); человекочитаемые поля (`.coords`, `.center/.radius`, `.normal/.offset/.direction`, `.vertex/.size/.side1/.side2`, `.endpoints`, `.vertices`, …); `Element.__getattr__` пробрасывает в `.data` | ~530 |
| `geo/lib_conic.py` | `Conic` (3×3 матрица `.matrix`), классификация по инвариантам, `as_ellipse/as_parabola/as_hyperbola/as_lines/as_point`, `Conic.from_string(equation)` | ~440 |
| `geo/lib_function.py` | `Function` — явная `y = f(x)` (`.expr`, `.var`, `.source`), sympy-парсинг, `If[...]` → `Piecewise`, цепочки `a ≤ x ≤ b`, `natural_singularities`, lambdify | ~290 |
| `geo/lib_implicit.py` | `ImplicitCurve` — произвольное `F(x, y) = 0` (`.expr`, `.var_x/.var_y`, `.source`), sympy-парсинг, lambdify на два аргумента | ~180 |
| `geo/curve_sampling.py` | Viewport-aware адаптивный сэмплер + Liang–Barsky-клиппинг; аналитика t-диапазонов для параболы/гиперболы; marching squares для implicit-кривых | ~370 |
| `geo/lib_commands.py` | 100+ геометрических операций, пересечения всех пар (включая numeric F/I), Conic-команды (Center/Focus/Vertex/Axes/Directrix/Polar/Tangent), Ellipse/Hyperbola/Parabola конструкторы, `function_T/conic_T/implicit_curve_T` для string-DSL | ~2200 |
| `geo/lib_vars.py` | `Measure(value, dimension)`, `AngleSize`, `Boolean(value)` | ~100 |
| `geo/utils.py` | is_number, is_angle_degrees, is_boolean | ~30 |
| `parsers/ggb_parser.py` | Извлечение XML из .ggb, парсинг конструкций, заполнение `ggb_raw`; `<expression type="conic/line/function/implicitpoly">` со знаком `=`; expressions внутри пропускаются через `dsl.run` | ~660 |
| `parsers/dsl/` | Python-DSL (exec-engine): `transform.py` (AST-rewriter, loop-scope, форма имён, forbid-list), `registrar.py` (`__reg__`/`__reg_loop__`/`__reg_tuple__` + ContextVar), `namespace.py` (FactoryDict с `__missing__` для ~74 автообнаруженных команд + math + `style/hide/show` helpers + forward-ref для `addVar`-переменных), `proxy.py` (ElementProxy с `__getattr__` в data и арифметикой `+/-/*/-/abs`), `sugar.py` (`f(x) = expr` pre-pass), `stub_gen.py` (`<scene>_stubs.pyi` после `loadGGB`). Entry: `dsl.run(constr, code)`, `with dsl.scope(c):`, `scene.putCode(code)`, `scene.loadCode(path)`. Стабы: `namespace.pyi`, `proxy.pyi`. | ~800 |
| `dsl.py` + `dsl.pyi` | Super-module — `from animageo.dsl import *` даёт все фабрики и типы в IDE | ~100 |
| `parsers/svg_parser.py` | Cairo-рендеринг manim-объектов в SVG | ~120 |

## Система зависимостей

Каждый элемент конструкции имеет **уровень** (level):

- **Level 0** --- свободные точки, заданные координатами
- **Level N** --- элементы, зависящие от элементов уровня N-1

```
Level 0:  A(0,0)   B(4,0)   C(0,3)
Level 1:  M = Midpoint(A, B)       s = Segment(A, B)
Level 2:  h = Segment(C, M)
```

При изменении элемента перестраиваются только те, кто от него зависит (ленивый rebuild).

## Расстановка подписей

`label_placement.py` работает в трёх режимах:

**1. Статический one-shot** (`auto_place_labels(scene)` / `scene.autoPlaceLabels()`):
- `compute_label_layout` (pure) собирает `LabelInfo` по всем видимым подписям, считает препятствия (segments, circles, point cloud), выбирает preferred direction для каждой подписи, запускает priority-ordered greedy solver по 8 кандидатам.
- Возвращает `dict[name, LabelPlacement]` без мутаций.
- `apply_label_layout` (impure) пишет результат в `elem.style['label_offset_px']` / `elem.style['label_anchor']` и перерендеривает сцену.
- Tex bbox кэшируется по `(text, font_size)` — keyframe-снимки и per-frame пересчёт переиспользуют измерения.

**2. `play_keyframes` + `keyframe_snapshots=true`**:
- Pre-pass: сохраняем `get_independents()` + visibility, проходим все keyframe (carry-forward values), на каждом вызываем `compute_label_layout`, собираем snapshots `list[dict[name, LabelPlacement]]`. Восстанавливаем состояние, делаем `rebuild(full=True)`.
- Перед реальным playback вызывается `_apply_keyframe_state(seq.keyframes[0], seq.element_info)`: значения и `show`/`hide` первого keyframe пишутся в construction, выполняется `geo.rebuild()`, затем `updateGeoElements()` обновляет затронутые mobject-ы. Это делает первый rendered frame независимым от сохраненного `.ggb` state.
- `KeyframeSequence.attach_label_layouts(layouts)` связывает снимки с интервалами: для `kind='static'` подписей создаёт `LabelOffsetInterpolator` (линейная или smooth интерполяция ggb-оффсета между снимками); для `kind='dynamic_angle'` — `AngleParams`, чтобы per-frame пересчитывать биссектрису.
- В `_play_keyframe_interval.on_frame` label-pass идёт ПОСЛЕ `geo.rebuild()` (чтобы `ang.side1/.side2/.vertex` были свежие) и ДО `updateGeoElements()` — метки рендерятся в том же `mob.become(CreateMObject(elem))`, что и геометрия.

**3. `autoPlaceLabels(dynamic=True)` под `addUpdater`**:
- Устанавливает `LabelTracker` (dict на сцене с `prev_offset`, `prev_anchor`, `anchor_flip_counter`, `angle_params`, `cfg`).
- `updateVar` после `geo.rebuild()` + `updateGeoElements()` дёргает `_apply_dynamic_labels`:
  - для dynamic-angle подписей — `compute_angle_label_center` без сглаживания (функция непрерывна сама по себе);
  - для статических — EMA (`apply_ema_step`) на offset + Schmitt-trigger на якорь (`anchor_hysteresis_step`);
  - троттлинг через `solver_every_n_frames`.

MC-канонизация (`canonicalize_anchor=true`) переписывает для каждой подписи `(anchor=A, offset=O_A) → (anchor='MC', offset=O_A - edge_A·halfExtent·ptUnit_ggb)`. Визуальный центр сохраняется, но якорь всегда один и тот же → интерполяция не даёт дискретных скачков при смене направления между keyframe. Off by default, чтобы не менять существующие snapshot-тесты.

**Угловая геометрия, учтённая в раскладке:**

- **Multi-arc:** подписи углов отодвигаются за внешнюю дужку при `elem.style['tick_count'] > 1` — эффективный радиус = `arc_size_px + (lines − 1) · ang_rshift`, та же формула используется рендером и раскладкой.
- **Два независимых зазора:** `angle_gap_arc_px` (дуга → подпись) и `angle_gap_sides_px` (стороны угла → bbox подписи для узких углов). Удалённый `angle_gap_px` больше не читается.
- **Авто-подбор радиуса дуги (`overlay.angle_radius`, default off):** `compute_effective_arc_size_px` общий для рендера (`animageo.py:CreateMObject`) и раскладки (`compute_label_layout` + `_collect_labels`). Формула `base · (pivot_rad / angle) ** exp`, зажатая в `[min_px, max_arm_fraction · min_arm_px]`. Подпись автоматически следует за скалированной дугой, т.к. источник числа один. Per-element escape: `elem.style['auto_radius'] = False`. Рендерер принимает `arc_size_px` через resolver; DSL-углы без explicit `elem.style['arc_size_px']` используют пиксельный путь через builtin default (17 px).

## Диспетчеризация команд

Функции в `lib_commands.py` именуются по шаблону:

```
{имя_команды}_{типы_аргументов}
```

Сокращения типов:

| Буква | Тип |
|-------|-----|
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
| `T` | str (DSL-литерал для строковых конструкторов) |

Примеры: `midpoint_pp`, `intersect_lc`, `rotate_pAp`, `distance_pp`,
`intersect_KK` (коника ∩ коника через pencil), `intersect_Kl` (коника ∩ прямая),
`intersect_FK` (функция ∩ коника через подстановку), `intersect_II`
(implicit ∩ implicit через marching squares + Newton), `center_K`,
`focus_K`, `polar_pK`, `tangent_pK`, `ellipse_ppi`, `parabola_pl`,
`conic_ppppp` (коника через 5 точек), `function_T` (Function("y = x²")).

Диспетчер (`Command.func()`) ищет функцию по имени в `globals()` модуля.

## Кривые высокого порядка: Conic, Function, ImplicitCurve

Три класса, покрывающие всё, что не сводится к линии/окружности/многоугольнику:

```
┌───────────────────────────────────────────────────────────────────┐
│ Conic (lib_conic.py)                                              │
│   matrix ∈ ℝ³ˣ³ симметричная  — (x, y, 1)·matrix·(x, y, 1)ᵀ = 0   │
│   Ленивая классификация по инвариантам det(matrix),               │
│   det(matrix₃₃), rank → 9 подтипов (circle / ellipse / parabola / │
│   hyperbola / intersecting_lines / parallel_lines / double_line / │
│   point / empty). Каноническая параметризация через               │
│   eigendecomposition matrix₃₃, разложение вырожденных через (±λ)  │
│   eigenvectors.                                                   │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ Function (lib_function.py)                                        │
│   sympy.Expr + свободная переменная; lambdify('numpy') один раз.  │
│   Препроцессор GGB → sympy: `^ → **`, `≤/≥ → <=/>=`,              │
│   цепочки `a ≤ x ≤ b → (a ≤ x) & (x ≤ b)`,                        │
│   `If[cond, then [, else]] → Piecewise((then, cond), …)`.         │
│   `natural_singularities` через `sympy.singularities`.            │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ ImplicitCurve (lib_implicit.py)                                   │
│   F(x, y) = 0 произвольной формы (полиномиальной или не).         │
│   `LHS = RHS` преобразуется в `(LHS) − (RHS) = 0`.                │
│   lambdify на два аргумента; NaN-безопасное вычисление.           │
└───────────────────────────────────────────────────────────────────┘
```

## Рендеринг кривых и клиппинг по холсту

Все три типа рендерятся через один общий слой в `curve_sampling.py`:

- **`sample_parametric(func, t_range, viewport, ...)`** — адаптивный
  сэмплер. Начинает с равномерной сетки в 32 точки; где шаг в scene MU
  превышает `segment_mu` (по умолчанию `3 / ptUnit`, т. е. 3 пикселя),
  вставляет середины длинных сегментов. **Hard cap** `max_samples=500`
  per-mobject гарантирует отсутствие зависаний на патологических
  выражениях. Клиппинг по viewport через **Liang–Barsky** с разрывом
  полилинии при выходе из кадра.
- **`viewport_t_ranges_parabola(...)` / `viewport_t_range_hyperbola_branch(...)`** —
  аналитически сужают t-диапазон до пересечения с viewport в канонической
  рамке коники. Парабола: `|u| ≤ 2·√(p·v_max)` (при `v_min > 0` — два
  диапазона). Гипербола (по ветви): `|t| ≤ min(acosh(u_max/a), asinh(v_max/b))`.
- **`marching_squares(F, viewport, grid_n=128)`** — классическая 16-случаев
  для `ImplicitCurve`. O(grid_n²) работы, константа — никаких
  зависаний. Линейная интерполяция зеросов на рёбрах клетки.

`CreateMObject` ветви:

| Тип | Стратегия | Комментарий |
|-----|-----------|-------------|
| `Conic (circle)` | `manim.Circle` с прямыми параметрами | замкнутый контур, заливка работает |
| `Conic (ellipse)` | `manim.Ellipse` + `.rotate().move_to(...)` | замкнутый контур, заливка работает |
| `Conic (parabola)` | `make_parabola_param` + `viewport_t_ranges_parabola` + `sample_parametric` | одна или две полилинии |
| `Conic (hyperbola)` | `make_hyperbola_branch_param` × 2 ветви | каждая ветвь — полилиния |
| `Conic (intersecting/parallel/double lines)` | `as_lines()` → `Line.get_endpoints(corners)` | переиспользует существующий рендер прямых |
| `Conic (point)` | `manim.Dot` | — |
| `Conic (empty)` | `None` | ничего не рисуется |
| `Function` | `(t, f(t))` как parametric + разбиение по `natural_singularities` + `sample_parametric` | `y = 1/x` даёт две полилинии, `tan(x)` — несколько кусков между разрывами |
| `ImplicitCurve` | `marching_squares` → список отрезков, каждый — `manim.Line` | лемнискаты, «сердца», тригонометрические узоры |

## Пересечения

Реализованы все нетривиальные пары:

| Пара | Метод | Функция |
|------|-------|---------|
| Conic ∩ Line | Подстановка параметризации прямой в `pᵀMp = 0` → квадратика | `intersect_Kl` |
| Conic ∩ Conic | Pencil: `det(λM₁ + M₂) = 0` → кубическая → разложение λ·M₁+M₂ в пару прямых → `intersect_Kl` | `intersect_KK` |
| Conic ∩ Circle | Circle → Conic адаптер + `intersect_KK` | `intersect_Kc` |
| Conic ∩ Arc/Segment/Ray | `intersect_Kl` + фильтр по принадлежности | `intersect_KC`/`Ks`/`Kr` |
| Function ∩ Line | Подстановка `y = f(x)` в уравнение прямой → 1D брент-поиск с sympy.solve fallback | `intersect_Fl` |
| Function ∩ Conic | Подстановка → 1D: `pᵀ·M·p` при `p = (x, f(x), 1)` | `intersect_FK` |
| Function ∩ Circle | `_circle_to_conic` + FK | `intersect_Fc` |
| Function ∩ Function | `f₁(x) − f₂(x) = 0` | `intersect_FF` |
| ImplicitCurve ∩ Line/Segment/Ray | Подстановка параметризации прямой в F → 1D | `intersect_Il/Is/Ir` |
| ImplicitCurve ∩ Conic/Circle/Function | Marching squares F₁ → вдоль каждого сегмента root-find F₂ → Newton-уточнение через `scipy.fsolve` | `intersect_IK/Ic/IF` |
| ImplicitCurve ∩ ImplicitCurve | То же самое | `intersect_II` |

Все функции имеют `*i` index-варианты для `Intersect[..., n]` и
обратные варианты (`_Kl`/`_lK`) для порядка аргументов.
