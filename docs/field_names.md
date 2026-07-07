# Имена полей и стилевых атрибутов — сквозная справка

Один референс для всех имён, которые встречаются в animageo:
- **Часть 1**: поля геометрических классов (`Point.x`, `Circle.center` и т. п.).
- **Часть 2**: типы элементов через 5 слоёв (GGB XML → animageo class → JSON → manim mobject → SVG).
- **Часть 3**: стилевые атрибуты через те же 5 слоёв.
- **Часть 4**: словарные перечисления (enum-значения).
- **Часть 5**: единицы измерения и константы конверсии.

Все переименования из коротких/абстрактных имён в человекочитаемые
завершены, **все backward-compat алиасы удалены**.

> **Как читать стилевое значение.** `elem.style` — только explicit-записи. Полное «что будет нарисовано» даёт resolver:
>
> ```python
> from animageo.style.resolver import resolve, resolved_style
>
> resolve(scene, elem, 'size_px')      # одно значение по цепочке приоритетов
> resolved_style(scene, elem)          # весь материализованный dict
> ```
>
> Цепочка: `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults.by_type → default=`. Все visual-ключи ниже могут лежать в `elem.style`, `elem.ggb_style`, `defaults.by_type` и `overlay.per_type` / `overlay.per_name`; resolver выбирает эффективное значение.

## Часть 1. Поля геометрических классов


## Финальные имена

### Point (`lib_elements.py:Point`)
| Поле | Тип | Смысл |
|---|---|---|
| `coords` | `np.ndarray([x, y])` | координаты (реальное поле) |
| `x` | `float` | x-координата (`@property` на coords[0]) |
| `y` | `float` | y-координата (`@property` на coords[1]) |

### Line
| Поле | Тип | Смысл |
|---|---|---|
| `normal` | `np.ndarray` | нормаль (единичный вектор) |
| `direction` | `np.ndarray` | направление (перпендикулярно нормали) |
| `offset` | `float` | знаковое расстояние до начала координат (в уравнении `normal·x = offset`) |

### Segment (наследует Line)
| Поле | Тип | Смысл |
|---|---|---|
| `endpoints` | `np.ndarray` shape (2, 2) | пара крайних точек |
| `start` | `np.ndarray` | первая точка (`@property` на endpoints[0]) |
| `end` | `np.ndarray` | вторая точка (`@property` на endpoints[1]) |
| `length` | `float` | длина |

### Ray (наследует Line)
| Поле | Тип | Смысл |
|---|---|---|
| `start` | `np.ndarray` | начало луча |
| `direction` | `np.ndarray` | направление (через Line) |

### Circle
| Поле | Тип | Смысл |
|---|---|---|
| `center` | `np.ndarray` | центр |
| `radius` | `float` | радиус |
| `radius_squared` | `float` | радиус² (computed `@property`) |

### Arc, CircleSector (наследуют Circle)
| Поле | Тип | Смысл |
|---|---|---|
| `angles` | `list[float, float]` | пара углов [start, end] |
| `angle_start` | `float` | `@property` на angles[0] |
| `angle_end` | `float` | `@property` на angles[1] |

### Angle
| Поле | Тип | Смысл |
|---|---|---|
| `vertex` | `np.ndarray` | вершина (точка) |
| `size` | `float` | размер в радианах |
| `side1` | `np.ndarray` | первая сторона (вектор) |
| `side2` | `np.ndarray` | вторая сторона |
| `arc_radius` | `float` | радиус рисуемой дуги |
| `start_angle` | `float` | угол от OX до side1 (радианы) |
| `end_angle` | `float` | угол от OX до side2 |
| `value` | `float` | синоним для `size` (`@property`) |

### Polygon
| Поле | Тип | Смысл |
|---|---|---|
| `vertices` | `np.ndarray` | массив вершин |

### Vector
| Поле | Тип | Смысл |
|---|---|---|
| `endpoints` | `np.ndarray` | пара точек [start, end] |
| `direction` | `np.ndarray` | направление (end − start) |
| `start` | `np.ndarray` | `@property` на endpoints[0] |
| `end` | `np.ndarray` | `@property` на endpoints[1] |

### Measure (`lib_vars.py:Measure`)
| Поле | Тип | Смысл |
|---|---|---|
| `value` | `float` | числовое значение |
| `dimension` | `int` | 0=скаляр, 1=длина, 2=площадь |

### AngleSize
| Поле | Тип | Смысл |
|---|---|---|
| `value` | `float` | размер в радианах |

### Boolean
| Поле | Тип | Смысл |
|---|---|---|
| `value` | `bool` | True/False |

### Conic (`lib_conic.py`)
| Поле | Тип | Смысл |
|---|---|---|
| `matrix` | `np.ndarray` (3×3) | симметричная матрица формы |
| `type` | `ConicType` | lazy-computed классификация |
| `kind` | `ConicType` | `@property` синоним для `type` |

### Function (`lib_function.py`), ImplicitCurve (`lib_implicit.py`)
| Поле | Тип | Смысл |
|---|---|---|
| `expr` | `sympy.Expr` | выражение: RHS для `Function`, нулевой уровень `F(x,y)=0` для `ImplicitCurve` |
| `var` (Function) / `var_x`, `var_y` (ImplicitCurve) | `sympy.Symbol` | символы переменных |
| `source` | `str` | исходная строка (для debug/repr) |
| `_callable` | `Callable` | numpy-lambdified |
| `natural_singularities` (Function) | `list[float]` | конечные реальные точки разрыва/неопределённости; renderer режет кривую по ним |
| `explicit_domain` (Function) | `tuple[float, float] \| None` | явный диапазон `x`, если задан пользователем |
| `expression`, `variable`, `callable` (Function) | — | `@property` алиасы для `expr`, `var`, `_callable` |
| `expression`, `x_var`, `y_var` (ImplicitCurve) | — | `@property` алиасы для `expr`, `var_x`, `var_y` |

### Var (`lib_vars.py:Var`)
| Поле | Тип | Смысл |
|---|---|---|
| `name` | `str` | имя переменной в Construction |
| `data` | `Any` | значение (`Measure`, `AngleSize`, `Boolean`, число и т. п.) |
| `style` | `StyleProxy` | технически есть, но переменные не рендерятся как геометрия |

### Element wrapper (`lib_elements.py:Element`, `parsers/dsl/proxy.py:ElementProxy`)
| Поле | Тип | Смысл |
|---|---|---|
| `name` | `str` | имя в Construction |
| `data` | `Any` | геометрический объект |
| `visible` | `bool` | видимость |
| `fixed` | `bool` | не перестраивается при `rebuild` |
| `tparam` | `Optional[float]` | curve/locus parameter для constrained точки (угол на окружности, линейный t на сегменте/прямой/луче) |
| `style` | `StyleProxy` | стиль |
| `ggb_raw` | `dict` | raw GGB-значения (до ImportPolicy) |
| `ggb_style` | `StyleProxy` | нормализованный GGB import-layer, отдельный от explicit `style` |
| `_visible` | `bool` | внутреннее хранилище видимости |
| `_visible_explicit` | `bool` | True после runtime/DSL-изменения `elem.visible`; защищает его от style layers |
| `_visible_has_value` | `bool` | True, если видимость была задана Construction/GGB/runtime |

### Construction (`lib_elements.py:Construction`) — методы
* `update_tparam(name, tparam)` — обновить `.tparam` constrained-точки и пометить зависимые для rebuild

### Construction (`geo/construction.py:Construction`) — основные поля
| Поле | Тип | Смысл |
|---|---|---|
| `phantoms` | `dict` | временные DSL-имена вида `_1`, `_2` |
| `vars` | `list[Var]` | числовые/булевы/угловые переменные |
| `elements` | `list[Element]` | геометрические элементы; по умолчанию содержит скрытые `xAxis`, `yAxis` |
| `commands` | `list[Command]` | отложенные команды построения и зависимости |
| `state` | `dict` | граф зависимостей: `level`, `inputs`, `outputs`, `input_commands`, `built` |
| `name_mapping` | `dict` | GGB-имя → нормализованный Python identifier |
| `naming_counters` | `dict` | счётчики DSL-регистратора для уникальных имён в циклах/функциях |
| `command_diagnostics` | `list[dict]` | диагностика unsupported-команд |
| `_command_diagnostic_keys` | `set` | внутренний dedupe для diagnostics |
| `_unsupported_roots_by_output` | `dict` | связь output → корневая unsupported-команда |
| `strict_unsupported` | `bool` | strict-режим: unsupported root command поднимает исключение |
| `log_unsupported` | `bool` | логировать unsupported-команды |

---

## Что изменилось с прошлых версий

Все переименования произошли в этой серии ревизий. Короткие имена
(`a`, `c`, `n`, `v`, `r`, `p`, `M`, `b`, `x`, `dim`,
`angle`, `original`, `points`, `end_points`, `start_point`) больше
не существуют — они полностью заменены на новые.

Wire-format JSON keyframe-анимации тоже использует новые имена:
`get_independents()` возвращает тип `'tparam_point'` и ключ `'tparam'`;
keyframe parser принимает только `'tparam'`.

## Внешние пользователи

Если есть пользовательский код, делавший `point.a`, `circle.c`,
`line.n`, `measure.x` и т. д., — эти обращения теперь
дадут `AttributeError`. Замените на соответствующие человечные
имена из таблицы выше. Это breaking change в public API.

---

## Часть 2. Типы элементов через 5 слоёв

Легенда колонок:
- **GGB XML** — тег/атрибут в файле `.ggb` (элемент внутри `<construction>`).
- **animageo class** — Python-класс в `animageo/geo/lib_*.py`.
- **JSON** — как тип идентифицируется в стилевом JSON (через `defaults` / `presets` / `import.per_type`).
- **manim mobject** — что создаёт `CreateMObject` для данного типа.
- **SVG** — итоговый тег в svg-выходе (через Cairo).

| Сущность | GGB XML | animageo class | JSON | manim mobject | SVG |
|---|---|---|---|---|---|
| Точка | `<element type="point">` | `Point` | `point_size`, `import.point_size`, `per_type: point` | `Circle` (radius) + опц. label | `<circle>` |
| Прямая | `<element type="line">` + `<coords a,b,c>` | `Line` | `line_width`, `per_type: line` | `Line` (clipped to viewport) | `<line>` |
| Отрезок | `<element type="segment">` | `Segment` | `line_width`, `tick`, `defaults.segment`, `per_type: segment` | `Line` + tick marks | `<line>` × N |
| Луч | `<element type="ray">` | `Ray` | `per_type: ray` | `Line` (clipped) | `<line>` |
| Вектор | `<element type="vector">` | `Vector` | `arrow`, `defaults.vector`, `per_type: vector` | `Arrow` + `CustomArrowTip` | `<path>` |
| Окружность | `<element type="circle">` | `Circle` | `per_type: circle` | `Circle` fill + `Circle` stroke (VGroup) | `<circle>` × 2 |
| Дуга | `<element type="arc">` | `Arc` | `per_type: arc` | `Arc` + опц. label | `<path>` |
| Сектор | `<element type="circlearc">` / `<element type="circlesector">` | `CircleSector` | `per_type: circlesector` | `Sector` + `Arc` + опц. label | `<path>` |
| Угол | `<element type="angle">` + `<arcSize>`, `<decoration>`, `<angleStyle>` | `Angle` | `angle_radius`, `defaults.angle`, `per_type: angle` | `AnnularSector` или `Polygon` (для right-angle) + label | `<path>` |
| Многоугольник | `<element type="polygon">` | `Polygon` | `per_type: polygon` | `Polygon` fill + `Polygon` stroke | `<polygon>` × 2 |
| Коника | `<element type="conic">` + `<matrix A0..A5>` | `Conic` (+ `ConicType` enum) | `per_type: conic` | `Circle`/`Ellipse`/`VMobject` (в зависимости от `.type`) | `<circle>`/`<ellipse>`/`<path>` |
| Функция | `<expression type="function" exp="y=…">` | `Function` | `per_type: function` | `VMobject` × N (кусочный sampling) | `<path>` |
| Неявная кривая | `<expression type="implicitpoly">` | `ImplicitCurve` | `per_type: implicitcurve` | `VMobject` × N (marching squares) | `<path>` |
| Число | `<element type="numeric">` | `Measure` (в `Var`) | — | — (невидимо) | — |
| Булево | — | `Boolean` (в `Var`) | — | — | — |
| Размер угла | `<element type="angle">` + value | `AngleSize` (в `Var`) | — | — | — |
| Метка | `<labelMode>`, `<caption>`, `<objColor>` | через `elem.style['label_*']` | `rendering.label_anchor`, `font_size`, `per_name: {...}` | `Tex` (через `create_label`) | `<text>` + `<path>` |

**Диспетчеризация команд** (`lib_commands.py`): имя команды = `{command_name}_{type_shortcuts}`, где шорткаты — `p=Point, l=Line, r=Ray, s=Segment, v=Vector, c=Circle, C=Arc, S=CircleSector, a=Angle, P=Polygon, K=Conic, F=Function, I=ImplicitCurve, i=int/float, m=Measure, A=AngleSize, b=Boolean, T=str`. Пример: `intersect_Kl(conic, line)`, `midpoint_pp(p1, p2)`.

---

## Часть 3. Стилевые атрибуты через 5 слоёв

Легенда:
- **GGB XML** — имя тега/атрибута в `.ggb`. `—` если в GGB нет эквивалента.
- **`elem.ggb_raw[...]`** — ключ в словаре сырых GGB-значений (до любой конверсии).
- **`elem.style[...]`** — ключ в runtime-словаре стиля после парсинга/политик.
- **JSON** — где это задаётся в стилевом JSON (если вообще). Canonical schema: reusable values live in `presets`, per-type application lives in `defaults.<type>.*`.
- **manim kwarg** — параметр, который реально передаётся в манимовский конструктор.
- **SVG** — атрибут в итоговом SVG.
- **Ед.** — единица измерения значения в `elem.style`.

### 3.0. Имена секций style JSON и renderer-config

Верхний уровень style JSON:

| Ключ | Тип | Смысл |
|---|---|---|
| `name` | `str` | необязательное имя стиля |
| `version` | `number` | версия пользовательского style-файла |
| `presets` | `dict` | semantic tokens: цвета, размеры, толщины, шрифт, tick/arrow структуры |
| `defaults` | `{type: {style_key: value}}` | per-type baseline, читается resolver после import-layer |
| `overlay` | `dict` | post-import overrides и автоматизмы |
| `rendering` | `dict` | настройки рендера/экспорта уровня сцены |
| `import` | `dict` | правила чтения GGB visual values |

`presets` из `builtin.json`:

| Группа | Ключи |
|---|---|
| `color` | `main`, `light`, `accent`, `accent_light`, `aux`, `black`, `white`, `shade`, `background`, `strong` |
| `point_size` | `main`, `bold`, `aux` |
| `line_width` | `main`, `bold`, `aux` |
| `angle_radius` | `main`, `bold`, `aux`, `shift`, `right` |
| `tick.main` | `tick_length_px`, `tick_width_px`, `tick_shift_px` |
| `arrow.main` | `arrow_length_px`, `arrow_width_px` |
| `font_size` | `main`, `bold`, `aux` |

`defaults` / `overlay.per_type` используют canonical type names:
`point`, `segment`, `line`, `ray`, `vector`, `angle`, `polygon`,
`circle`, `arc`, `circlesector`, `conic`, `function`, `implicitcurve`.
`defaults.decoration` есть в `builtin.json` как shared helper для tick presets,
но это не drawable element type.

`overlay`:

| Ключ | Подключи | Смысл |
|---|---|---|
| `per_type` | `<type> → style keys` | правила для всех элементов типа, выше `elem.ggb_style` |
| `per_name` | `<name> → style keys` | правила для конкретного элемента, выше `per_type` |
| `angle_radius` | `enabled`, `exp`, `pivot_rad`, `min_px`, `max_arm_fraction`, `apply_to_right` | авто-масштабирование радиуса дуг углов |
| `label_placement` | `enabled`, `distance_px`, `padding_px`, `angle_gap_arc_px`, `angle_gap_sides_px`, `w_anchor`, `w_label`, `w_geom`, `dynamic_angles`, `keyframe_snapshots`, `canonicalize_anchor`, `interpolation`, `ema_alpha`, `anchor_flip_frames`, `solver_every_n_frames` | авто-раскладка подписей, включая keyframe/per-frame режимы |

`rendering`:

| Ключ | Значения | Смысл |
|---|---|---|
| `background` | hex или `color.*` | фон Manim camera, MP4 и SVG export |
| `line_cap` | `butt` / `round` / `square` | default для `stroke_linecap` |
| `right_angle_joint` | `auto` / `bevel` / `miter` / `round` | default для `right_angle_joint` у маркера прямого угла |
| `polygon_boundary_layer` | `top` / `null` | поднимает сегменты-стороны полигона на `z_index=10` |
| `points_display` | `auto` / `only_labels` / `only_points` | глобальный режим точки+подпись |
| `label_anchor` | `TL`..`BR` | сценовый default-якорь подписи |
| `label_value_precision` | `int` | сценовый default-точность value-подписей |

`reference`:

| Ключ | Тип | Смысл |
|---|---|---|
| `reference.width` | `float` | ширина эталонного холста стиля для preview/export-layout |
| `reference.height` | `float` | высота эталонного холста стиля |
| `reference.source` | `manual` / `source_view` / `ggb_view` | откуда взят reference-холст; runtime-область конструкции задается через `content.source` |

`import`:

| Ключ | Тип | Смысл |
|---|---|---|
| `enabled` | `bool` | `false` отключает `elem.ggb_style`, `colors`, `point_size`, `line_width`, `policy`; geometry/raw остаются |
| `colors` | `{"#hex [opacity]": "preset-or-#hex [opacity]"}` | палитровый remap GGB colors |
| `point_size` | `{raw_or_style_size: value}` | remap размера точки в `size_px` |
| `line_width` | `{raw_or_style_width: value}` | remap толщины линии в `stroke_width_px` |
| `policy` | `dict` | ImportPolicy fields: `size_px`, `stroke_width_px`, `arc_size_px`, `label_offset_px`, `label_color`, `label_visible`, `visible`, `label_text`, `label_mode`, `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator`, `angle_range`, `tick_count`, `font_size`, `font_size_px`, `stroke`, `fill`, `fill_opacity`, `point_shape`, `stroke_opacity`, `stroke_dash_ratio`, `stroke_linecap` |

### 3.1. Геометрические размеры

| Концепт | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim kwarg | SVG | Ед. |
|---|---|---|---|---|---|---|---|
| Диаметр точки | `<pointSize val>` | `point_size` | `size_px` | `point_size.*`, `import.point_size` | `radius = size_px/2/ptUnit` | `r` | px |
| Толщина линии | `<lineStyle thickness>` | `line_thickness` | `stroke_width_px` | `line_width.*`, `import.line_width` | `stroke_width = 100*val/ptUnit` | `stroke-width` | px |
| Радиус дуги угла | `<arcSize val>` | `arc_size` | `arc_size_px` | `angle_radius.*`, `defaults.angle.arc_size_px`, `overlay.angle_radius` | `radius = arc_size_px/ptUnit` (для right-angle делится на √2) | — | px |
| Сдвиг между концентрич. дугами | — | — | `arc_shift_px` | `angle_radius.shift`, `defaults.angle.arc_shift_px` | — | — | px |
| Радиус волны tick | — | — | `tick_radius_px` | `per_name` / `overlay` | `radius` в `round_corners_vmobject` | — | px |
| Размер правого угла | — | — | `right_angle_size_px` | `angle_radius.right`, `defaults.angle.right_angle_size_px` | `radius` для Polygon | — | px |
| Штрихи равенства | `<decoration type>` | `decoration_lines` | `tick_length_px`, `tick_width_px`, `tick_shift_px` | `tick.*`, `defaults.segment`, `defaults.vector` | `length/shift = px/ptUnit`; `tick_width_px → stroke_width_to_manim()` | — | px |
| Наконечник стрелки | — | — | `arrow_length_px`, `arrow_width_px` | `arrow.*`, `defaults.vector` | `CustomArrowTip` | — | px |

### 3.2. Обводка и заливка (SVG-совместимые имена)

| Концепт | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim kwarg | SVG |
|---|---|---|---|---|---|---|
| Цвет обводки | `<objColor r,g,b>` (зависит от типа) | `obj_color` | `stroke` | `color.*`, `import.colors`, `import.policy.stroke` | `color` | `stroke` |
| Прозрачность обводки | `<lineStyle opacity>` | `line_opacity` | `stroke_opacity` | `import.colors` (c opacity), `import.policy.stroke_opacity` | `stroke_opacity` | `opacity` |
| Пунктир (доля) | `<lineStyle type>` (>0) | `line_type` | `stroke_dash_ratio` | `import.policy` (DSL) | `dashed_ratio=val, dash_length=0.17` | `stroke-dasharray` |
| Концы линий | — | — | `stroke_linecap` | `rendering.line_cap` | `cap_style` | `stroke-linecap` |
| Цвет заливки | `<objColor>` (для angle/polygon/arc/conic/point) | `obj_color` | `fill` | `color.*`, `import.colors`, `import.policy.fill` | `fill_color` | `fill` |
| Прозрачность заливки | `<objColor alpha>` | `obj_color['alpha']` / `obj_color['opacity']` | `fill_opacity` | `import.colors` (c target-opacity), `import.policy.fill_opacity` | `fill_opacity` | `fill-opacity` |

### 3.3. Точки (форма и декомпозиция GGB-пресета)

`import.colors` нормализует результат как отдельные поля: `stroke` / `fill`
получают только hex `#rrggbb`, а `stroke_opacity` / `fill_opacity` меняются
только если opacity явно указана в правой части mapping. Например
`"#1565c0 0.1": "color.accent 1"` превращает цвет в `#f15b5b` и
ставит opacity `1.0`; `"#1565c0 0.1": "color.accent"` сохраняет
старую opacity элемента.

| Концепт | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim kwarg | SVG |
|---|---|---|---|---|---|---|
| Форма точки | `<pointStyle val="0..10">` (жёстко связано с заливкой) | `point_style` (int) | `point_shape` (str enum) | `import.policy.point_shape`, `overlay.per_type.point.point_shape` | `_make_point_mobject` (9 форм: circle, square, diamond, triangle_\*, cross, plus) | зависит от формы |

GGB-код `point_style` раскладывается в три независимых оси (`point_shape`, `fill`/`fill_opacity`, `stroke`/`stroke_width_px`/`stroke_opacity`) через `style/enums.py:_GGB_POINT_STYLE_PATCHES`.

| GGB `pointStyle` | `point_shape` | Заливка | Обводка |
|---|---|---|---|
| `0` (закрашенный, чёрный контур — дефолт) | `"circle"` | цвет | `#000000`, 1 px |
| `2` (полый кружок) | `"circle"` | нет (`fill_opacity=0`) | цвет, 2 px |
| `10` (закрашенный без контура) | `"circle"` | цвет | нет (`stroke_opacity=0`) |
| `4` (закрашенный ромб) | `"diamond"` | цвет | нет |
| `5` (полый ромб) | `"diamond"` | нет | цвет, 2 px |
| `1` (×) | `"cross"` | нет | цвет, 2 px |
| `3` (+) | `"plus"` | нет | цвет, 2 px |
| `6`/`7`/`8`/`9` (▲/▼/▶/◀) | `"triangle_up"` / `"triangle_down"` / `"triangle_right"` / `"triangle_left"` | цвет | нет |

### 3.4. Углы

| Концепт | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim |
|---|---|---|---|---|---|
| Какую дугу рисовать | `<angleStyle val="1\|2">` | `angle_style` | `angle_range` (`"minor"` / `"reflex"`) | `import.policy.angle_range`, `overlay.per_name` | логика выбора в CreateMObject |
| Правый угол (квадратик) | auto | — | `right_angle_marker` (bool) | `overlay.per_name` | `Polygon` маркер вместо `AnnularSector` |
| Количество дуг/галочек | `<decoration type>` | `decoration_lines` | `tick_count` (int) | `import.policy.tick_count`, `overlay.per_name` | цикл в CreateMObject |
| Стиль галочек (для Segment/Vector) | — | — | `tick_style` (`"line"` / `"wave"`) | `overlay.per_name` | `Line` vs `round_corners_vmobject` |
| Толщина дуги | `<lineStyle thickness>` (как у линии) | `line_thickness` | `stroke_width_px` | `line_width.*`, `defaults.angle.stroke_width_px` | `stroke_width` |
| Стык прямого угла | — | — | `right_angle_joint` | `rendering.right_angle_joint`, `overlay.per_name` / `per_type` | `joint_type` у `VMobject` прямого угла |

### 3.5. Лейблы

| Концепт | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim |
|---|---|---|---|---|---|
| Текст | `<labelMode>`, `<caption>` | `label_caption` | `label_text` | `import.policy.label_text`, `overlay.per_name` | `Tex(text)` |
| Режим текста | `<labelMode val>` | `label_mode` (`0/1/2/3/9`) | `label_mode` (`label` / `value` / `label_value`) | `import.policy.label_mode`, `overlay.per_type`, `overlay.per_name` | выбирает `label`, `value` или `label = value` |
| Формат значения | — | — | `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator` | `overlay.per_type`, `overlay.per_name`, `import.policy.*` | форматирует численную часть |
| Видимость | `<show label>` | `show_label` | `label_visible` | `defaults.<type>.label_visible`, `overlay.per_type`, `overlay.per_name`, `import.policy.label_visible` | (условное создание) |
| Цвет | `<objColor>` (тот же) | `obj_color.hex` | `label_color` | `import.policy.label_color` | `color` на `Tex` |
| Шрифт (размер) | `<gui><font size>` (scene-wide) | — | `font_size_px` | `font_size.*`, `defaults.<type>.font_size_px`, `import.policy.font_size_px` | `font_size` |
| Якорь | `<labelingStyle>` (scene-wide) | — | `label_anchor` (`"TL"..."BR"`) | `rendering.label_anchor`, `overlay.per_name` | `aligned_edge` в `move_to` |
| Смещение | `<labelOffset x,y>` | `label_offset_px` (инвертируется Y) | `label_offset_px` (после инверсии Y) | `import.policy.label_offset_px`, `overlay.per_name` | `tex.shift(...)` |
| Радиальное смещение (угол) | — | — | `label_radial_offset_px` | `overlay.per_name` | добавляется к `r` для Angle |
| Замороженная позиция | — | — | `label_placement_locked` (bool) | `overlay.per_name` | solver пропускает |
| Внутренний флаг авто-раскладки | — | — | `_auto_placed` (bool, internal) | — | отключает GGB descender correction в `create_label` |

### 3.6. Видимость и слои

| Концепт | GGB XML | `elem.ggb_raw` | elem.(style/attr) | JSON |
|---|---|---|---|---|
| Видимость элемента | `<show object>` | `show_object` | `elem.visible` (wrapper attr) / resolver key `visible` | `import.policy.visible`, `overlay.per_type`, `overlay.per_name`, `defaults.<type>.visible` |
| Z-index | — | — | `elem.style['z_index']` (float) | `rendering.polygon_boundary_layer`, `overlay.per_name` |
| Z-index заливки (CircleSector) | — | — | `elem.style['z_index_fill']` | `overlay.per_name` |

### 3.7. GGB Graphics View: сетка, оси, фон

Эти поля читаются из `<euclidianView>` в `geogebra.xml` и сохраняются в
`scene.style.export`, а не в `elem.ggb_style`: это настройки области просмотра,
не свойства отдельных геометрических объектов.

| Концепт | GGB XML | `style.export` | Рендер |
|---|---|---|---|
| Размер viewport | `<size width height>` | `ptWidth`, `ptHeight` | camera / SVG size |
| Начало координат и масштаб | `<coordSystem xZero yZero scale yscale>` | `ptXZero`, `ptYZero`, `ptUnit`, `ptUnit_ggb`, `ptYUnit_ggb` | camera transform, source view |
| Показать оси | `<evSettings axes>` | `showAxes` | включает `_coordinate_background` axes |
| Показать сетку | `<evSettings grid>` | `showGrid` | включает `_coordinate_background` grid |
| Жирная сетка | `<evSettings gridIsBold>` | `gridIsBold` | немного увеличивает толщину сетки |
| Тип сетки | `<evSettings gridType>` | `gridType` | сохраняется; сейчас рендерится декартова сетка |
| Цвет фона | `<bgColor r g b>` | `background` | сохраняется как hex |
| Цвет осей | `<axesColor r g b>` | `axesColor` | линии осей, ticks, числа |
| Цвет сетки | `<gridColor r g b>` | `gridColor` | линии сетки |
| Стиль линий | `<lineStyle axes grid>` | `axesLineStyle`, `gridLineStyle` | сохраняется для совместимости |
| Ось X/Y | `<axis id="0|1" ...>` | `axes.x`, `axes.y` | per-axis show / numbers / ticks |
| Шаг сетки | `<grid distX distY distTheta>` | `gridDistX`, `gridDistY`, `gridDistTheta` | `distX/distY` задают шаг сетки |

`_coordinate_background` рисуется до геометрии: сетка на `z_index=-20`,
оси на `z_index=-10`, деления и числа на `z_index=-9`. Это не то же самое,
что служебные `xAxis` / `yAxis` в `Construction`.

---

## Часть 4. Словарные перечисления (enums)

Определены в `animageo/style/enums.py` как `Literal`-типы + runtime-кортеж для валидации.

| Тип | Значения | Где используется |
|---|---|---|
| `PointShape` | `"circle"`, `"square"`, `"diamond"`, `"triangle_up"`, `"triangle_down"`, `"triangle_left"`, `"triangle_right"`, `"cross"`, `"plus"` | `elem.style['point_shape']` |
| `AngleRange` | `"minor"`, `"reflex"` | `elem.style['angle_range']` |
| `TickStyle` | `"line"`, `"wave"` | `elem.style['tick_style']` |
| `PointDisplay` | `"auto"`, `"only_labels"`, `"only_points"` | `rendering.points_display` |
| `LineCap` | `"butt"`, `"round"`, `"square"` | `rendering.line_cap`, `elem.style['stroke_linecap']` |
| `RightAngleJoint` | `"auto"`, `"bevel"`, `"miter"`, `"round"` | `rendering.right_angle_joint` |
| `LabelAnchor` | `"TL"`, `"TC"`, `"TR"`, `"ML"`, `"MC"`, `"MR"`, `"BL"`, `"BC"`, `"BR"` | `rendering.label_anchor`, `elem.style['label_anchor']` |
| `Interpolation` | `"linear"`, `"smooth"` | `overlay.label_placement.interpolation` |

---

## Часть 5. Единицы измерения и константы конверсии

### 5.1. Единицы

| Пространство | Единица | Где встречается |
|---|---|---|
| GGB-экранные пиксели | px | GGB XML-значения (pointSize, thickness, arcSize, labelOffset), `elem.ggb_raw`, суффикс `_px` в `elem.style` |
| JSON-стилевые единицы | px-подобные (подставляются пользователем) | `presets`, `defaults.*` |
| Internal/manim coordinate units (MU) | 1 MU = `ptUnit` пикселей | радиусы, координатные длины, смещения |
| Manim stroke/font render units | stroke/font шкала Manim | `stroke_width`, `set_stroke(width=...)`, `font_size` |
| Безразмерные | `[0..1]` opacity, ratio | `stroke_opacity`, `fill_opacity`, `stroke_dash_ratio` |
| Перечисления | строки | см. Часть 4 |

**Pixel-invariance contract:** все `_px`-значения хранятся как пиксели, но конвертируются по назначению Manim-параметра. Координатные размеры (`size_px`, `arc_size_px`, `tick_length_px`, `tick_shift_px`, `tick_radius_px`, `arrow_*_px`, offsets) становятся MU через `/ ptUnit`. Толщины и шрифты, передаваемые в Manim `stroke_width`, `set_stroke(width=...)` или `font_size`, идут через render-scale `* 100 / ptUnit`: `stroke_width_px`, `tick_width_px`, `font_size_px`. Это гарантирует одинаковый визуальный результат при любом размере канваса.

### 5.2. Константы (`animageo/constants.py`)

| Константа | Значение | Назначение |
|---|---|---|
| `STYLE_TO_INTERNAL` | `0.02` | Константа внутреннего масштабирования; runtime style JSON использует pixel-unit `*_px` |
| `LINE_WIDTH_SCALE` | `2` | Константа внутреннего масштабирования ширин; рендер читает `stroke_width_px` через resolver |
| `FONT_SIZE_RATIO` | `50/25.9 ≈ 1.93` | Константа внутреннего масштабирования шрифтов; рендер читает `font_size_px` через resolver |
| `STROKE_WIDTH_SCALE` | `100` | `elem.style['stroke_width_px']` → manim `stroke_width` (делится на `ptUnit`) |
| `GGB_FONT_SCALE` | `100.0` | GGB font px → manim `font_size` (делится на `ptUnit`) |
| `Z_FILL`, `Z_FILL_INNER`, `Z_FILL_LABEL`, `Z_ANGLE`, `Z_LINE`, `Z_STROKE`, `Z_POINT`, `Z_LABEL` | tiers | z-index по типам элементов (дефолты) |

`builtin.json` (`animageo/style/builtin.json`) — package-shipped per-type дефолты в пикселях; `StyleConfig.load(user_path)` всегда начинает с него и сливает user JSON через `deep_merge`.

### 5.3. Примеры полных цепочек

**Точка A из GGB** (`pointSize=5`, цвет `#1565c0`, `pointStyle=0`):
```
GGB XML:
    <pointSize val="5"/>
    <objColor r="21" g="101" b="192"/>
    <pointStyle val="0"/>
    <labelOffset x="-28" y="32"/>

↓ ggb_parser + style/enums.ggb_point_style_to_elem_style

elem.ggb_raw = {
    'point_size': 5, 'point_style': 0,
    'obj_color': {
        'r': 21, 'g': 101, 'b': 192,
        'alpha': 0, 'opacity': 0, 'hex': '#1565c0'
    },
    'label_offset_px': [-28, 32],
}
elem.style = {
    'size_px': 10.0,              # 5 × 2
    'point_shape': 'circle',
    'fill': '#1565c0',   'fill_opacity': 1.0,
    'stroke': '#000000', 'stroke_width_px': 1.0, 'stroke_opacity': 1.0,
    'label_color': '#1565c0',
    'label_offset_px': [-28, -32],  # Y инвертируется
    ...
}

↓ CreateMObject (render time, ptUnit = 50)

Circle(radius=0.1, color='#000000', fill_color='#1565c0',
       fill_opacity=1, stroke_opacity=1, stroke_width=2)

↓ Cairo → SVG

<circle cx="…" cy="…" r="0.1"
        fill="#1565c0" fill-opacity="1"
        stroke="#000000" stroke-width="2"/>
```

**Пунктирная линия из GGB** (`thickness=10`, `type=1`):
```
GGB XML:
    <lineStyle thickness="10" type="1" opacity="255"/>
elem.style = {
    'stroke_width_px': 5.0,        # 10 / 2
    'stroke_opacity':  1.0,        # 255 / 255
    'stroke_dash_ratio': 0.65,     # type > 0 → 0.65
    ...
}

↓ CreateMObject (ptUnit = 50)

DashedLine(..., stroke_width=10, dashed_ratio=0.65, dash_length=0.17)

↓ SVG

<path stroke="…" stroke-width="10" stroke-dasharray="..."/>
```

---

## См. также

- `docs/styles.md` — человекочитаемый гайд по JSON-схеме с примерами.
- `animageo/style/enums.py` — исходный код с enum-значениями и GGB-декомпозицией.
- `animageo/style/proxy.pyi` — полный список ключей `elem.style` с IDE-аннотациями типов.
- `animageo/style/schema.py` — docstring с каноническим примером JSON + валидатор.
