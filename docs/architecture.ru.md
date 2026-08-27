# Архитектура

Смежные документы:

- `docs/styles.md` — основной справочник по стилям и распределению ответственности между слоями.
- `docs/import_policies.md` — подробности импорта и адаптации GGB, `ImportPolicy`.
- `docs/field_names.md` — таблица соответствий GGB XML → `ggb_raw` → `ggb_style` / `elem.style` → JSON и рендер.
- `docs/guide/index.html` — интерактивное руководство на русском языке (стилизация в §5–§7, справочник в §11). Его нужно открывать через локальный веб-сервер — на GitHub оно не отрисовывается.

## Конвейер обработки

```
 файл .ggb (ZIP с XML)                     код Python DSL (строка / .py)
       |                                          |
       v                                          v
 ┌─────────────┐                         ┌────────────────┐
 │ ggb_parser  │────┐                    │ parsers/dsl/   │
 └─────────────┘    │                    │ (движок exec)  │
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
 │   + GeoStyle     (контекст экспорта)   │
 │   + StyleConfig  (builtin.json +       │
 │                    JSON пользователя)  │
 │   + ImportPolicy (GGB raw → ggb_style) │
 └──────┬─────────────────────────────────┘
        |
        v                  addAllGeometry:
 ┌──────────────┐
 │ CreateMObject│◄─── читает через resolver.resolve:
 │   ──> mobject│          │   elem.style → per_name → per_type →
 └──────┬───────┘          │   ggb_style → defaults
        |                  v
        |
┌───────┴───────┐
v               v
┌───────────┐  ┌───────────┐
│ svg_parser│  │   manim   │
│  (Cairo)  │  │ рендерер  │
└─────┬─────┘  └─────┬─────┘
      v              v
   .svg           .mp4
```

Парсер сохраняет сырые значения GGB в `elem.ggb_raw` (`point_size`, `point_style`, `line_thickness`, `line_type`, `line_opacity`, `arc_size`, `label_offset_px`, `obj_color`, а также флаги подписей и видимости — `label_mode`, `label_caption`, `show_object`, `show_label`). В `obj_color` хранятся исходные `r/g/b/alpha` вместе с удобными псевдонимами `hex` и `opacity`. Нормализованные визуальные ключи попадают в `elem.ggb_style`; как именно адаптировать сырые значения дальше, решает `ImportPolicy` — «как в GGB», фиксированное значение, вызываемый объект, квантование или переназначение. Resolver подключает этот слой только при `import.enabled != false`.

### Подсистема стилей: три слоя

```
Приоритет чтения (resolver.resolve(scene, elem, key)):

 1. elem.style[key]              ← явные записи (DSL/API)
 2. overlay.per_name[name][key]  ← точечное правило для одного элемента
 3. overlay.per_type[type][key]  ← правило для всех элементов типа
 4. elem.ggb_style[key]          ← импорт и адаптация GGB, если включены
 5. defaults.by_type[type][key]  ← базовые значения типа (builtin.json + JSON)
 6. неявный elem.style[key]      ← внутренний стиль геометрического класса
 7. default= из аргумента вызова ← жёсткий запасной вариант
```

У каждого слоя одна зона ответственности:

- **`DefaultsProfile`** — поставляемый с пакетом `builtin.json` плюс JSON пользователя (глубокое слияние). Базовые значения по типам в **пикселях** (`size_px`, `stroke_width_px`, `arc_size_px`, …). Никогда не пишет в `elem.style`.
- **`StyleOverlay`** — `per_type` и `per_name` плюс автоматика (`angle_radius`, `label_placement`). Логически стоит выше импорта GGB и значений по умолчанию; resolver читает overlay напрямую из `StyleConfig`.
- **`GGBImportPolicy`** (то есть `ImportPolicy`) — только преобразования GGB: `scale:`, `quantize:`, `remap:` над `elem.ggb_raw`, результат сохраняется в `elem.ggb_style`. Элементы DSL пропускаются — у них сырой слой пуст.

Контракт единиц измерения: любой ключ `*_px` в `elem.style`, `elem.ggb_style` и `defaults.<type>` задан в **пикселях**. Рендерер делит на `ptUnit` в момент отрисовки. Устаревшие поля `GeoStyle.ang_rdefault / ang_rshift / ang_right / dot_size` тоже хранят пиксели.

## Модули

| Модуль | Роль |
|--------|------|
| `animageo.py` | Сцена, анимации, `CreateMObject` (диспетчер + рендереры `_render_<type>` по типам + `_build_render_ctx` + `_renderer_for` + `_make_label`), `loadGGB`, подключение ImportPolicy |
| `__main__.py` | Точка входа CLI (`python -m animageo file.ggb -o out.svg`): ветка статического вектора (svg/pdf/eps/tikz) и ветка рендера через manim (png/gif/mp4/webm/mov, `--keyframes` для анимации) |
| `ui.py` | Шаблоны TeX, `create_label` (девять точек привязки), `ValueLabel` (быстрые числовые подписи на основе DecimalNumber) и `prewarm_decimal_glyphs`, `install_cyrillic_tex_template`, NumberedFrame, CustomArrowTip |
| `labels.py` | Итоговое разрешение текста подписи: `resolve_label_text`, `resolve_label_spec` (структурированный `LabelSpec` для быстрой ветки числовых подписей), режимы подписи (имя / значение / имя + значение) |
| `constants.py` | Уровни z-index (Z_FILL, Z_LINE, Z_POINT, Z_LABEL) и коэффициенты масштабирования |
| `keyframes.py` | Анимация по ключевым кадрам: разбор JSON, интерполяторы, easing, `LabelOffsetInterpolator` и `attach_label_layouts` |
| `label_placement.py` | Автоматическое размещение подписей: жадный решатель по 8 кандидатам, `compute_label_layout` (чистая функция), `apply_label_layout` (с побочными эффектами), `compute_angle_label_center`, `compute_effective_arc_size_px` (angle_radius), LRU-кэш bbox, помощники EMA и гистерезиса |
| `export_layout.py` | Раскладка холста экспорта: `ExportLayout`, `compute_export_layout`, нормализация размера, вписывания, якоря и отступов для параметров экспорта |
| `render_config.py` | `configure_render` (формат вывода, fps, прозрачность) и починка палитры GIF |
| `logging_config.py` | Помощник `configure_logging`, на котором держатся флаги CLI `--verbose`, `--quiet`, `--log-level` |
| `style/__init__.py` | `GeoStyle` (контейнер уровня сцены: палитра, параметры экспорта, флаги рендера), утилиты работы с цветом, реэкспорт констант и масштабирования |
| `style/config.py` | `StyleConfig` (верхний уровень), `DefaultsProfile`, `StyleOverlay`, `deep_merge` для слияния нескольких JSON-файлов; `resolve_style_input` (превращает короткое имя пресета в путь к упакованному JSON; пути и словари проходят насквозь) и `available_style_presets` |
| `style/presets/*.json` | Пресеты стилей, поставляемые с пакетом (`default`, `book_blue`, `book_green`, `book_purple`, `book_red`), выбираются по имени через `resolve_style_input` |
| `style/resolver.py` | `resolve(scene, elem, key)`, `resolved_style(scene, elem)` и `trace(…)` для отладки цепочки |
| `style/builtin.json` | Значения по умолчанию по типам в пикселях, поставляемые с пакетом; загружаются всегда, JSON пользователя накладывается сверху |
| `style/schema.py` | Документация и валидация JSON-стилей и секций `import_policy` (плюс `overlay` в NEW_TOP_KEYS) |
| `style/scaling.py` | Именованные функции преобразования: GGB px ↔ JSON-стиль ↔ внутренние единицы |
| `style/import_policy.py` | Датакласс `ImportPolicy` — преобразования только для GGB (`scale:`, `quantize:`, `remap:`) |
| `style/dsl.py` | Мини-DSL для значений JSON: `const:`, `scale:`, `quantize:`, `remap:` |
| `style/ggb_resolver.py` | `resolve_ggb_style(ggb_raw)` — воспроизводит слой импортированного стиля GGB для точного режима |
| `style/animatable.py` | Реестр анимируемых ключей `elem.style` для стилевых дорожек keyframes v2 (вид интерполяции для каждого ключа; без зависимости от manim) |
| `style/colorspace.py` | Преобразование sRGB ↔ Oklab и интерполяция цвета для стилевых дорожек ключевых кадров (без зависимости от manim) |
| `style/enums.py` | Словари значений стиля (псевдонимы `Literal` плюс кортежи времени выполнения) и таблица разложения `pointStyle` из GGB на форму, заливку и обводку |
| `style/proxy.py` + `proxy.pyi` | `StyleProxy` — наследник dict с доступом к `elem.style` через атрибуты и отслеживанием явных записей |
| `geo/construction.py` | Граф зависимостей, топологическая сортировка (алгоритм Кана), пересборка, применение, `update_tparam`, `rename`, `add_and_build` |
| `geo/lib_elements.py` | Point, Line, Segment, Ray, Angle, Polygon, Circle, Arc, CircleSector, Vector, LocusCurve, Text (плюс реэкспорт Conic/Function/ImplicitCurve); понятные человеку поля (`.coords`, `.center/.radius`, `.normal/.offset/.direction`, `.vertex/.size/.side1/.side2`, `.endpoints`, `.vertices`, …); `Element.__getattr__` перенаправляет обращения в `.data` |
| `geo/lib_conic.py` | `Conic` (матрица 3×3 `.matrix`), классификация по инвариантам, `as_ellipse/as_parabola/as_hyperbola/as_lines/as_point`, `Conic.from_string(equation)` |
| `geo/lib_function.py` | `Function` — явная зависимость `y = f(x)` (`.expr`, `.var`, `.source`), разбор через sympy, `If[...]` → `Piecewise`, цепочки `a ≤ x ≤ b`, `natural_singularities`, lambdify |
| `geo/lib_implicit.py` | `ImplicitCurve` — произвольное `F(x, y) = 0` (`.expr`, `.var_x/.var_y`, `.source`), разбор через sympy, lambdify с двумя аргументами |
| `geo/curve_sampling.py` | Адаптивная выборка с учётом области видимости и отсечение по Лианг — Барски; аналитические диапазоны t для параболы и гиперболы; marching squares для неявных кривых |
| `geo/lib_commands.py` | Геометрические операции (более 400 записей в `COMMAND_REGISTRY`): пересечения всех пар (включая численные F/I), команды для кривых второго порядка (Center/Focus/Vertex/Axes/Directrix/Polar/Tangent), конструкторы Ellipse/Hyperbola/Parabola, `function_T/conic_T/implicit_curve_T` для строкового DSL |
| `geo/lib_vars.py` | `Measure(value, dimension)`, `AngleSize`, `Boolean(value)` |
| `geo/tparam.py` | Математика перехода «точка ↔ параметр кривой» (tparam) для всех типов путей; основа `Construction.tparam_from_coords` и системы ключевых кадров |
| `geo/utils.py` | is_number, is_angle_degrees, is_boolean |
| `parsers/ggb_parser.py` | Извлечение XML из .ggb, разбор конструкции, заполнение `ggb_raw`; `<expression type="conic/line/function/implicitpoly">` со знаком `=`; выражения внутри проходят через `dsl.run` |
| `parsers/ggb_macro.py` | Раскрытие макросов пользовательских инструментов: разбирает определения из `geogebra_macro.xml` и подставляет вызовы макросов примитивными командами перед разбором (поддерживается рекурсивное раскрытие) |
| `parsers/ggb_generator.py` | Создаёт архивы .ggb из Construction (сериализация в XML GeoGebra плюс упаковка в ZIP) |
| `parsers/dsl/` | Python DSL (движок exec): `transform.py` (переписывание AST, области видимости циклов, формирование имён, список запретов), `registrar.py` (`__reg__`/`__reg_loop__`/`__reg_tuple__` и ContextVar), `namespace.py` (FactoryDict с `__missing__` для 99 автоматически найденных фабрик команд поверх 433 сигнатур диспетчеризации, плюс математика, помощники `style/hide/show` и упреждающие ссылки на переменные `addVar`), `proxy.py` (ElementProxy с `__getattr__` в data и арифметикой `+/-/*//` и `abs`), `sugar.py` (предобработка `f(x) = expr`), `stub_gen.py` (`<scene>_stubs.pyi` после `loadGGB`). Точки входа: `dsl.run(constr, code)`, `with dsl.scope(c):`, `scene.putCode(code)`, `scene.loadCode(path)`. Заглушки: `namespace.pyi`, `proxy.pyi`. |
| `dsl.py` + `dsl.pyi` | Супермодуль — `from animageo.dsl import *` даёт в IDE все фабрики и типы |
| `parsers/svg_parser.py` | Отрисовка объектов manim в SVG через Cairo |
| `exporters/tikz/` | Семантический экспорт TikZ (`scene.exportTikZ`): обходит отрисовываемые элементы в порядке z и выдаёт нативный TikZ через тот же resolver стилей, что и рендерер |
| `exporters/jsxgraph/` | Интерактивный экспорт JSXGraph (`scene.exportJSXGraph`): транслирует граф конструкции в живые вызовы `board.create`; на выходе html/js/spec/json/moodle |
| `exporters/construction_summary.py` | Компактная JSON-сводка конструкции для генерации стиля с помощью AI (`construction_to_ai_summary`, `write_ai_summary`) |

## Система зависимостей

У каждого элемента конструкции есть **уровень**:

- **Уровень 0** --- свободные точки, заданные координатами
- **Уровень N** --- элементы, зависящие от элементов уровня N-1

```
Уровень 0:  A(0,0)   B(4,0)   C(0,3)
Уровень 1:  M = Midpoint(A, B)       s = Segment(A, B)
Уровень 2:  h = Segment(C, M)
```

При изменении элемента пересобираются только зависящие от него (ленивая пересборка).

## Размещение подписей

`label_placement.py` работает в трёх режимах:

**1. Однократное статическое размещение** (`auto_place_labels(scene)` / `scene.autoPlaceLabels()`):
- `compute_label_layout` (чистая функция) собирает `LabelInfo` по всем видимым подписям, накапливает препятствия (отрезки, окружности, облако точек), выбирает для каждой подписи предпочтительное направление и запускает жадный решатель по 8 кандидатам в порядке приоритета.
- Возвращает `dict[name, LabelPlacement]` без изменения состояния.
- `apply_label_layout` (с побочными эффектами) записывает результат в `elem.style['label_offset_px']` и `elem.style['label_anchor']` и перерисовывает сцену.
- Bbox формулы Tex кэшируется по паре `(text, font_size)` — снимки ключевых кадров и покадровый пересчёт переиспользуют измерения.

**2. `play_keyframes` при `keyframe_snapshots=true`**:
- Предварительный проход: сохраняются `get_independents()` и видимость, обходятся все ключевые кадры (значения переносятся вперёд), на каждом вызывается `compute_label_layout`, снимки накапливаются в `list[dict[name, LabelPlacement]]`. Затем состояние восстанавливается и выполняется `rebuild(full=True)`.
- Перед самим воспроизведением вызывается `_apply_keyframe_state(seq.keyframes[0], seq.element_info)`: значения первого кадра и его `show`/`hide` записываются в конструкцию, выполняется `geo.rebuild()`, после чего `updateGeoElements()` обновляет затронутые mobject'ы. Благодаря этому первый отрисованный кадр не зависит от состояния, сохранённого в `.ggb`.
- `KeyframeSequence.attach_label_layouts(layouts)` привязывает снимки к интервалам: для подписей с `kind='static'` создаётся `LabelOffsetInterpolator` (линейная или сглаженная интерполяция смещения ggb между снимками), для `kind='dynamic_angle'` — `AngleParams`, чтобы биссектриса пересчитывалась на каждом кадре.
- В `_play_keyframe_interval.on_frame` проход по подписям выполняется ПОСЛЕ `geo.rebuild()` (чтобы `ang.side1/.side2/.vertex` были свежими) и ДО `updateGeoElements()` — подписи отрисовываются тем же вызовом `mob.become(CreateMObject(elem))`, что и геометрия.

**3. `autoPlaceLabels(dynamic=True)` под `addUpdater`**:
- Устанавливается `LabelTracker` — словарь на сцене с полями `prev_offset`, `prev_anchor`, `anchor_flip_counter`, `angle_params`, `cfg`.
- `updateVar` после `geo.rebuild()` и `updateGeoElements()` вызывает `_apply_dynamic_labels`:
  - для подписей динамических углов — `compute_angle_label_center` без сглаживания (функция и так непрерывна);
  - для статических подписей — EMA (`apply_ema_step`) по смещению плюс триггер Шмитта по якорю (`anchor_hysteresis_step`);
  - троттлинг через `solver_every_n_frames`.

Канонизация MC (`canonicalize_anchor=true`) переписывает каждую подпись из `(anchor=A, offset=O_A)` в `(anchor='MC', offset=O_A - edge_A·halfExtent·ptUnit_ggb)`. Визуальный центр сохраняется, но якорь всегда один и тот же → интерполяция не даёт скачков, когда направление меняется между кадрами. По умолчанию выключено, чтобы существующие снимочные тесты продолжали проходить.

**Геометрия угла, которую учитывает раскладка:**

- **Несколько дуг.** Подписи углов отодвигаются за самую внешнюю дугу, когда `elem.style['tick_count'] > 1` — эффективный радиус равен `arc_size_px + (lines − 1) · ang_rshift`; ту же формулу используют и рендерер, и раскладка.
- **Два независимых зазора.** `angle_gap_arc_px` (дуга → подпись) и `angle_gap_sides_px` (стороны угла → bbox подписи для узких углов). Убранный общий ключ `angle_gap_px` больше не читается.
- **Автоматическое масштабирование радиуса дуги** (`overlay.angle_radius`, по умолчанию выключено): `compute_effective_arc_size_px` используется совместно рендерером (`animageo.py:CreateMObject`) и раскладкой (`compute_label_layout` и `_collect_labels`). Формула `base · (pivot_rad / angle) ** exp` с ограничением диапазоном `[min_px, max_arm_fraction · min_arm_px]`. Подпись автоматически следует за масштабированной дугой, потому что число берётся из одного источника. Отключение для отдельного элемента: `elem.style['auto_radius'] = False`. Рендерер получает `arc_size_px` через resolver; углы, созданные в DSL без явного `elem.style['arc_size_px']`, идут по пиксельному пути через значение по умолчанию из builtin (17 px).

## Диспетчеризация команд

Функции в `lib_commands.py` названы по образцу:

```
{имя_команды}_{типы_аргументов}
```

Сокращения типов:

| Буква | Тип |
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
| `T` | str (литерал DSL для конструкторов со строковым аргументом) |

Примеры: `midpoint_pp`, `intersect_lc`, `rotate_pAp`, `distance_pp`,
`intersect_KK` (кривая ∩ кривая методом пучка), `intersect_Kl` (кривая ∩ прямая),
`intersect_FK` (функция ∩ кривая подстановкой), `intersect_II`
(неявная ∩ неявная через marching squares и метод Ньютона), `center_K`,
`focus_K`, `polar_pK`, `tangent_pK`, `ellipse_ppi`, `parabola_pl`,
`conic_ppppp` (кривая второго порядка по пяти точкам), `function_T` (Function("y = x²")).

Диспетчер (`Command.func()`) ищет имя в `COMMAND_REGISTRY`, который заполняется функциями модуля во время импорта.

## Кривые высших порядков: Conic, Function, ImplicitCurve

Три класса покрывают всё, что не сводится к прямой, окружности или многоугольнику:

```
┌───────────────────────────────────────────────────────────────────┐
│ Conic (lib_conic.py)                                              │
│   matrix ∈ ℝ³ˣ³ симметрична — (x, y, 1)·matrix·(x, y, 1)ᵀ = 0     │
│   Ленивая классификация по инвариантам det(matrix),               │
│   det(matrix₃₃) и рангу → 9 подтипов (circle / ellipse /          │
│   parabola / hyperbola / intersecting_lines / parallel_lines /    │
│   double_line / point / empty). Каноническая параметризация       │
│   через спектральное разложение matrix₃₃; вырожденные случаи      │
│   раскладываются по собственным векторам (±λ).                    │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ Function (lib_function.py)                                        │
│   sympy.Expr плюс свободная переменная; lambdify('numpy') ровно   │
│   один раз. Препроцессор GGB → sympy: `^ → **`, `≤/≥ → <=/>=`,    │
│   цепочки `a ≤ x ≤ b → (a ≤ x) & (x ≤ b)`,                        │
│   `If[cond, then [, else]] → Piecewise((then, cond), …)`.         │
│   `natural_singularities` через `sympy.singularities`.            │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│ ImplicitCurve (lib_implicit.py)                                   │
│   F(x, y) = 0 произвольного вида — полином или нет.               │
│   `LHS = RHS` нормализуется в `(LHS) − (RHS) = 0`.                │
│   Lambdify с двумя аргументами; вычисление, устойчивое к NaN.     │
└───────────────────────────────────────────────────────────────────┘
```

## Отрисовка кривых и отсечение по области видимости

Все три типа отрисовываются через один общий слой в `curve_sampling.py`:

- **`sample_parametric(func, t_range, viewport, ...)`** — адаптивная
  выборка. Начинается с равномерной сетки из 32 точек; там, где шаг в
  единицах сцены превышает `segment_mu` (по умолчанию `3 / ptUnit`, то есть
  3 пикселя), в длинные отрезки вставляются середины. **Жёсткий предел**
  `max_samples=500` на mobject гарантирует, что патологические выражения не
  подвесят рендер. Отсечение по области видимости — **алгоритмом
  Лианг — Барски**, ломаная разрывается при выходе за кадр.
- **`viewport_t_ranges_parabola(...)` и `viewport_t_range_hyperbola_branch(...)`** —
  аналитически сужают диапазон t до пересечения с областью видимости в
  канонической системе координат кривой. Парабола: `|u| ≤ 2·√(p·v_max)`
  (при `v_min > 0` получается два диапазона). Гипербола (для каждой ветви):
  `|t| ≤ min(acosh(u_max/a), asinh(v_max/b))`.
- **`marching_squares(F, viewport, grid_n=128)`** — классический алгоритм на
  16 случаев для `ImplicitCurve`. Объём работы O(grid_n²) при постоянной
  памяти — зависаний не бывает. Нули на рёбрах ячеек находятся линейной
  интерполяцией.

Ветвление в `CreateMObject`:

| Тип | Стратегия | Примечания |
|------|----------|-------|
| `Conic (circle)` | `manim.Circle` с прямыми параметрами | замкнутый контур, заливка работает |
| `Conic (ellipse)` | `manim.Ellipse` + `.rotate().move_to(...)` | замкнутый контур, заливка работает |
| `Conic (parabola)` | `make_parabola_param` + `viewport_t_ranges_parabola` + `sample_parametric` | одна или две ломаные |
| `Conic (hyperbola)` | `make_hyperbola_branch_param` × 2 ветви | каждая ветвь — ломаная |
| `Conic (intersecting/parallel/double lines)` | `as_lines()` → `Line.get_endpoints(corners)` | переиспользует готовый рендерер прямых |
| `Conic (point)` | `manim.Dot` | — |
| `Conic (empty)` | `None` | ничего не рисуется |
| `Function` | `(t, f(t))` как параметрическая кривая + разбиение по `natural_singularities` + `sample_parametric` | `y = 1/x` даёт две ломаные, `tan(x)` — несколько кусков между разрывами |
| `ImplicitCurve` | `marching_squares` → список отрезков, каждый — `manim.Line` | лемнискаты, «сердечки», тригонометрические узоры |

## Пересечения

Реализованы все нетривиальные пары:

| Пара | Метод | Функция |
|------|--------|----------|
| Conic ∩ Line | Подстановка параметризации прямой в `pᵀMp = 0` → квадратное уравнение | `intersect_Kl` |
| Conic ∩ Conic | Пучок: `det(λM₁ + M₂) = 0` → кубическое уравнение → разложение λ·M₁+M₂ на пару прямых → `intersect_Kl` | `intersect_KK` |
| Conic ∩ Circle | Адаптер Circle → Conic плюс `intersect_KK` | `intersect_Kc` |
| Conic ∩ Arc/Segment/Ray | `intersect_Kl` плюс фильтр принадлежности | `intersect_KC`/`Ks`/`Kr` |
| Function ∩ Line | Подстановка `y = f(x)` в уравнение прямой → сначала `sympy.solve`, затем скан по смене знака с запасным делением пополам | `intersect_Fl` |
| Function ∩ Conic | Подстановка → одномерная задача: `pᵀ·M·p` при `p = (x, f(x), 1)` | `intersect_FK` |
| Function ∩ Circle | `_circle_to_conic` плюс FK | `intersect_Fc` |
| Function ∩ Function | `f₁(x) − f₂(x) = 0` | `intersect_FF` |
| ImplicitCurve ∩ Line/Segment/Ray | Подстановка параметризации прямой в F → одномерная задача | `intersect_Il/Is/Ir` |
| ImplicitCurve ∩ Conic/Circle/Function | Marching squares для F₁ → поиск корней F₂ вдоль каждого отрезка → уточнение методом Ньютона через `scipy.fsolve` | `intersect_IK/Ic/IF` |
| ImplicitCurve ∩ ImplicitCurve | Тот же подход | `intersect_II` |

У всех функций есть варианты с индексом `*i` для `Intersect[..., n]` и
варианты с переставленными аргументами (`_Kl` / `_lK`).
