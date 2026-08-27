# Имена полей и атрибутов стиля — сквозной справочник

Один справочник на все имена, которые встречаются в animageo:
- **Часть 1**: поля геометрических классов (`Point.x`, `Circle.center` и т. д.).
- **Часть 2**: типы элементов в пяти слоях (GGB XML → класс animageo → JSON → mobject manim → SVG).
- **Часть 3**: атрибуты стиля в тех же пяти слоях.
- **Часть 4**: словарные перечисления (значения enum).
- **Часть 5**: единицы измерения и константы преобразования.

О том, откуда взялись эти имена (короткие имена до версии 1.0 и их удаление),
см. приложение [История](#history) в конце.

> **Как прочитать значение стиля.** В `elem.style` лежат только явные записи. Полный ответ на вопрос «что будет нарисовано» даёт resolver:
>
> ```python
> from animageo.style.resolver import resolve, resolved_style
>
> resolve(scene, elem, 'size_px')      # одно значение по цепочке приоритетов
> resolved_style(scene, elem)          # весь материализованный словарь
> ```
>
> Цепочка: `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults.by_type → default=`. Любой визуальный ключ из перечисленных ниже может жить в `elem.style`, `elem.ggb_style`, `defaults.by_type` и `overlay.per_type` / `overlay.per_name`; resolver выбирает действующее значение.

## Часть 1. Поля геометрических классов

### Point (`lib_elements.py:Point`)
| Поле | Тип | Смысл |
|---|---|---|
| `coords` | `np.ndarray([x, y])` | координаты (настоящее поле) |
| `x` | `float` | координата x (`@property` над coords[0]) |
| `y` | `float` | координата y (`@property` над coords[1]) |

### Line
| Поле | Тип | Смысл |
|---|---|---|
| `normal` | `np.ndarray` | нормаль (единичный вектор) |
| `direction` | `np.ndarray` | направление (перпендикулярно нормали) |
| `offset` | `float` | расстояние до начала координат со знаком (в уравнении `normal·x = offset`) |

### Segment (наследует Line)
| Поле | Тип | Смысл |
|---|---|---|
| `endpoints` | `np.ndarray` формы (2, 2) | пара концевых точек |
| `start` | `np.ndarray` | первая точка (`@property` над endpoints[0]) |
| `end` | `np.ndarray` | вторая точка (`@property` над endpoints[1]) |
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
| `radius_squared` | `float` | радиус² (вычисляемое `@property`) |

### Arc, CircleSector (наследуют Circle)
| Поле | Тип | Смысл |
|---|---|---|
| `angles` | `list[float, float]` | пара углов [начало, конец] |
| `angle_start` | `float` | `@property` над angles[0] |
| `angle_end` | `float` | `@property` над angles[1] |

### Angle
| Поле | Тип | Смысл |
|---|---|---|
| `vertex` | `np.ndarray` | вершина (точка) |
| `size` | `float` | величина в радианах |
| `side1` | `np.ndarray` | первая сторона (вектор) |
| `side2` | `np.ndarray` | вторая сторона |
| `arc_radius` | `float` | радиус отрисованной дуги |
| `start_angle` | `float` | угол от OX до side1 (радианы) |
| `end_angle` | `float` | угол от OX до side2 |
| `value` | `float` | синоним `size` (`@property`) |

### Polygon
| Поле | Тип | Смысл |
|---|---|---|
| `vertices` | `np.ndarray` | массив вершин |

### Vector
| Поле | Тип | Смысл |
|---|---|---|
| `endpoints` | `np.ndarray` | пара точек [начало, конец] |
| `direction` | `np.ndarray` | направление (конец − начало) |
| `start` | `np.ndarray` | `@property` над endpoints[0] |
| `end` | `np.ndarray` | `@property` над endpoints[1] |

### Measure (`lib_vars.py:Measure`)
| Поле | Тип | Смысл |
|---|---|---|
| `value` | `float` | числовое значение |
| `dimension` | `int` | 0=скаляр, 1=длина, 2=площадь |

### AngleSize
| Поле | Тип | Смысл |
|---|---|---|
| `value` | `float` | величина в радианах |

### Boolean
| Поле | Тип | Смысл |
|---|---|---|
| `value` | `bool` | True/False |

### Conic (`lib_conic.py`)
| Поле | Тип | Смысл |
|---|---|---|
| `matrix` | `np.ndarray` (3×3) | симметричная матрица формы |
| `type` | `ConicType` | классификация, вычисляемая лениво |
| `kind` | `ConicType` | `@property`, синоним `type` |

### Function (`lib_function.py`), ImplicitCurve (`lib_implicit.py`)
| Поле | Тип | Смысл |
|---|---|---|
| `expr` | `sympy.Expr` | выражение: правая часть для `Function`, нулевой уровень `F(x,y)=0` для `ImplicitCurve` |
| `var` (Function) / `var_x`, `var_y` (ImplicitCurve) | `sympy.Symbol` | символы переменных |
| `source` | `str` | исходная строка (для отладки и repr) |
| `_callable` | `Callable` | скомпилировано через lambdify для numpy |
| `natural_singularities` (Function) | `list[float]` | конечные вещественные точки разрыва или неопределённости; рендерер разбивает по ним кривую |
| `explicit_domain` (Function) | `tuple[float, float] \| None` | явный диапазон `x`, если задан пользователем |
| `expression`, `variable`, `callable` (Function) | — | `@property`-псевдонимы для `expr`, `var`, `_callable` |
| `expression`, `x_var`, `y_var` (ImplicitCurve) | — | `@property`-псевдонимы для `expr`, `var_x`, `var_y` |

### Var (`lib_vars.py:Var`)
| Поле | Тип | Смысл |
|---|---|---|
| `name` | `str` | имя переменной в Construction |
| `data` | `Any` | значение (`Measure`, `AngleSize`, `Boolean`, число и т. д.) |
| `style` | `StyleProxy` | технически присутствует, но переменные не отрисовываются как геометрия |

### Обёртка Element (`lib_elements.py:Element`, `parsers/dsl/proxy.py:ElementProxy`)
| Поле | Тип | Смысл |
|---|---|---|
| `name` | `str` | имя в Construction |
| `data` | `Any` | сам геометрический объект |
| `visible` | `bool` | видимость |
| `fixed` | `bool` | не пересобирается во время `rebuild` |
| `tparam` | `Optional[float]` | параметр кривой или локуса у связанной точки (угол на окружности, линейный t на отрезке, прямой, луче) |
| `style` | `StyleProxy` | стиль |
| `ggb_raw` | `dict` | сырые значения GGB (до ImportPolicy) |
| `ggb_style` | `StyleProxy` | нормализованный слой импорта GGB, отдельный от явного `style` |
| `_visible` | `bool` | внутреннее хранилище видимости |
| `_visible_explicit` | `bool` | True после изменения `elem.visible` во время выполнения или из DSL; защищает его от слоёв стиля |
| `_visible_has_value` | `bool` | True, когда видимость задана из Construction, GGB или во время выполнения |

### Construction (`lib_elements.py:Construction`) — методы
* `update_tparam(name, tparam)` — обновить `.tparam` у связанной точки и пометить зависимые элементы на пересборку

### Construction (`geo/construction.py:Construction`) — основные поля
| Поле | Тип | Смысл |
|---|---|---|
| `phantoms` | `dict` | временные имена DSL вида `_1`, `_2` |
| `vars` | `list[Var]` | числовые, логические и угловые переменные |
| `elements` | `list[Element]` | геометрические элементы; по умолчанию содержит скрытые `xAxis`, `yAxis` |
| `commands` | `list[Command]` | отложенные команды построения и зависимости |
| `state` | `dict` | граф зависимостей: `level`, `inputs`, `outputs`, `input_commands`, `built` |
| `name_mapping` | `dict` | имя GGB → нормализованный идентификатор Python |
| `naming_counters` | `dict` | счётчики регистратора DSL для уникальных имён в циклах и функциях |
| `command_diagnostics` | `list[dict]` | диагностика неподдерживаемых команд |
| `_command_diagnostic_keys` | `set` | внутренняя защита от дублей в диагностике |
| `_unsupported_roots_by_output` | `dict` | связь «выход → корневая неподдерживаемая команда» |
| `strict_unsupported` | `bool` | строгий режим: корневая неподдерживаемая команда бросает исключение |
| `log_unsupported` | `bool` | логировать неподдерживаемые команды |

---

## Часть 2. Типы элементов в пяти слоях

Что означают столбцы:
- **GGB XML** — тег или атрибут в файле `.ggb` (элемент внутри `<construction>`).
- **Класс animageo** — класс Python в `animageo/geo/lib_*.py`.
- **JSON** — как тип обозначается в JSON-стиле (через `defaults`, `presets`, `import.per_type`).
- **mobject manim** — что создаёт `CreateMObject` для этого типа.
- **SVG** — итоговый тег в выводе SVG (через Cairo).

| Сущность | GGB XML | Класс animageo | JSON | mobject manim | SVG |
|---|---|---|---|---|---|
| Точка | `<element type="point">` | `Point` | `point_size`, `import.point_size`, `per_type: point` | `Circle` (радиус) плюс подпись при необходимости | `<circle>` |
| Прямая | `<element type="line">` плюс `<coords a,b,c>` | `Line` | `line_width`, `per_type: line` | `Line` (отсечён по области видимости) | `<line>` |
| Отрезок | `<element type="segment">` | `Segment` | `line_width`, `tick`, `defaults.segment`, `per_type: segment` | `Line` плюс засечки | `<line>` × N |
| Луч | `<element type="ray">` | `Ray` | `per_type: ray` | `Line` (отсечён) | `<line>` |
| Вектор | `<element type="vector">` | `Vector` | `arrow`, `defaults.vector`, `per_type: vector` | `Arrow` плюс `CustomArrowTip` | `<path>` |
| Окружность | `<element type="circle">` | `Circle` | `per_type: circle` | `Circle` заливки плюс `Circle` обводки (VGroup) | `<circle>` × 2 |
| Дуга | `<element type="arc">` | `Arc` | `per_type: arc` | `Arc` плюс подпись при необходимости | `<path>` |
| Сектор | `<element type="circlearc">` / `<element type="circlesector">` | `CircleSector` | `per_type: circlesector` | `Sector` плюс `Arc` плюс подпись при необходимости | `<path>` |
| Угол | `<element type="angle">` плюс `<arcSize>`, `<decoration>`, `<angleStyle>` | `Angle` | `angle_radius`, `defaults.angle`, `per_type: angle` | `AnnularSector` или `Polygon` (для прямых углов) плюс подпись | `<path>` |
| Многоугольник | `<element type="polygon">` | `Polygon` | `per_type: polygon` | `Polygon` заливки плюс `Polygon` обводки | `<polygon>` × 2 |
| Кривая 2-го порядка | `<element type="conic">` плюс `<matrix A0..A5>` | `Conic` (плюс enum `ConicType`) | `per_type: conic` | `Circle`/`Ellipse`/`VMobject` (в зависимости от `.type`) | `<circle>`/`<ellipse>`/`<path>` |
| Функция | `<expression type="function" exp="y=…">` | `Function` | `per_type: function` | `VMobject` × N (кусочная выборка) | `<path>` |
| Неявная кривая | `<expression type="implicitpoly">` | `ImplicitCurve` | `per_type: implicitcurve` | `VMobject` × N (marching squares) | `<path>` |
| Число | `<element type="numeric">` | `Measure` (внутри `Var`) | — | — (невидимо) | — |
| Логическое значение | — | `Boolean` (внутри `Var`) | — | — | — |
| Величина угла | `<element type="angle">` плюс значение | `AngleSize` (внутри `Var`) | — | — | — |
| Подпись | `<labelMode>`, `<caption>`, `<objColor>` | через `elem.style['label_*']` | `rendering.label_anchor`, `font_size`, `per_name: {...}` | `Tex` (через `create_label`) | `<text>` плюс `<path>` |

**Диспетчеризация команд** (`lib_commands.py`): имя команды = `{имя_команды}_{сокращения_типов}`, где сокращения — `p=Point, l=Line, r=Ray, s=Segment, v=Vector, c=Circle, C=Arc, S=CircleSector, a=Angle, P=Polygon, K=Conic, F=Function, I=ImplicitCurve, i=int/float, m=Measure, A=AngleSize, b=Boolean, T=str`. Пример: `intersect_Kl(conic, line)`, `midpoint_pp(p1, p2)`.

---

## Часть 3. Атрибуты стиля в пяти слоях

Что означают столбцы:
- **GGB XML** — имя тега или атрибута в `.ggb`. `—`, когда в GGB нет соответствия.
- **`elem.ggb_raw[...]`** — ключ в словаре сырых значений GGB (до любых преобразований).
- **`elem.style[...]`** — ключ в словаре стиля времени выполнения после разбора и политик.
- **JSON** — где это задаётся в JSON-стиле (если задаётся вообще). Каноническая схема: переиспользуемые значения живут в `presets`, применение по типам — в `defaults.<type>.*`.
- **Аргумент manim** — параметр, который реально передаётся в конструктор manim.
- **SVG** — атрибут в итоговом SVG.
- **Единица** — единица измерения значения в `elem.style`.

### 3.0. Имена секций JSON-стиля и конфигурации рендерера

Верхний уровень JSON-стиля:

| Ключ | Тип | Смысл |
|---|---|---|
| `name` | `str` | необязательное имя стиля |
| `version` | `number` | версия пользовательского файла стиля |
| `presets` | `dict` | семантические токены: цвета, размеры, толщины, шрифт, структуры засечек и стрелок |
| `defaults` | `{type: {style_key: value}}` | базовые значения по типам, читаются resolver'ом после слоя импорта |
| `overlay` | `dict` | переопределения поверх импорта и автоматика |
| `rendering` | `dict` | настройки рендера и экспорта уровня сцены |
| `import` | `dict` | правила чтения визуальных значений GGB |

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

В `defaults` и `overlay.per_type` используются канонические имена типов:
`point`, `segment`, `line`, `ray`, `vector`, `angle`, `polygon`,
`circle`, `arc`, `circlesector`, `conic`, `function`, `implicitcurve`.
`defaults.decoration` есть в `builtin.json` как общий помощник для пресетов
засечек, но отрисовываемым типом элемента он не является.

`overlay`:

| Ключ | Подключи | Смысл |
|---|---|---|
| `per_type` | `<тип> → ключи стиля` | правила для всех элементов типа, выше `elem.ggb_style` |
| `per_name` | `<имя> → ключи стиля` | правила для конкретного элемента, выше `per_type` |
| `angle_radius` | `enabled`, `exp`, `pivot_rad`, `min_px`, `max_arm_fraction`, `apply_to_right` | автоматическое масштабирование радиусов дуг углов |
| `label_placement` | `enabled`, `distance_px`, `padding_px`, `angle_gap_arc_px`, `angle_gap_sides_px`, `w_anchor`, `w_label`, `w_geom`, `dynamic_angles`, `keyframe_snapshots`, `canonicalize_anchor`, `interpolation`, `ema_alpha`, `anchor_flip_frames`, `solver_every_n_frames` | автоматическая раскладка подписей, включая режимы ключевых кадров и покадровый |

`rendering`:

| Ключ | Значения | Смысл |
|---|---|---|
| `background` | hex или `color.*` | фон камеры Manim, MP4 и экспорта SVG |
| `line_cap` | `butt` / `round` / `square` | значение по умолчанию для `stroke_linecap` |
| `right_angle_joint` | `auto` / `bevel` / `miter` / `round` | значение по умолчанию для `right_angle_joint` маркера прямого угла |
| `polygon_boundary_layer` | `top` / `null` | поднимает стороны многоугольника на `z_index=10` |
| `points_display` | `auto` / `only_labels` / `only_points` | глобальный режим отображения точек и подписей |
| `label_anchor` | `TL`..`BR` | якорь подписи по умолчанию для всей сцены |
| `label_value_precision` | `int` | точность числовых подписей по умолчанию для всей сцены |

`reference`:

| Ключ | Тип | Смысл |
|---|---|---|
| `reference.width` | `float` | ширина эталонного холста стиля для раскладки превью и экспорта |
| `reference.height` | `float` | высота эталонного холста стиля |
| `reference.source` | `manual` / `source_view` / `ggb_view` | откуда взят эталонный холст; область конструкции во время выполнения задаётся через `content.source` |

`import`:

| Ключ | Тип | Смысл |
|---|---|---|
| `enabled` | `bool` | `false` отключает `elem.ggb_style`, `colors`, `point_size`, `line_width`, `policy`; геометрия и сырые значения остаются |
| `colors` | `{"#hex [opacity]": "пресет-или-#hex [opacity]"}` | переназначение палитры цветов GGB |
| `point_size` | `{сырой_или_стилевой_размер: значение}` | переназначение размера точки в `size_px` |
| `line_width` | `{сырая_или_стилевая_толщина: значение}` | переназначение толщины линии в `stroke_width_px` |
| `policy` | `dict` | поля ImportPolicy: `size_px`, `stroke_width_px`, `arc_size_px`, `label_offset_px`, `label_color`, `label_visible`, `visible`, `label_text`, `label_mode`, `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator`, `angle_range`, `tick_count`, `font_size`, `font_size_px`, `stroke`, `fill`, `fill_opacity`, `point_shape`, `stroke_opacity`, `stroke_dash_ratio`, `stroke_linecap` |

### 3.1. Геометрические размеры

| Понятие | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | Аргумент manim | SVG | Единица |
|---|---|---|---|---|---|---|---|
| Диаметр точки | `<pointSize val>` | `point_size` | `size_px` | `point_size.*`, `import.point_size` | `radius = size_px/2/ptUnit` | `r` | px |
| Толщина линии | `<lineStyle thickness>` | `line_thickness` | `stroke_width_px` | `line_width.*`, `import.line_width` | `stroke_width = 100*val/ptUnit` | `stroke-width` | px |
| Радиус дуги угла | `<arcSize val>` | `arc_size` | `arc_size_px` | `angle_radius.*`, `defaults.angle.arc_size_px`, `overlay.angle_radius` | `radius = arc_size_px/ptUnit` (для прямых углов делится на √2) | — | px |
| Сдвиг между концентрическими дугами | — | — | `arc_shift_px` | `angle_radius.shift`, `defaults.angle.arc_shift_px` | — | — | px |
| Радиус волны засечки | — | — | `tick_radius_px` | `per_name` / `overlay` | `radius` в `round_corners_vmobject` | — | px |
| Размер маркера прямого угла | — | — | `right_angle_size_px` | `angle_radius.right`, `defaults.angle.right_angle_size_px` | `radius` для Polygon | — | px |
| Засечки равенства | `<decoration type>` | `decoration_lines` | `tick_length_px`, `tick_width_px`, `tick_shift_px` | `tick.*`, `defaults.segment`, `defaults.vector` | `length/shift = px/ptUnit`; `tick_width_px → stroke_width_to_manim()` | — | px |
| Наконечник стрелки | — | — | `arrow_length_px`, `arrow_width_px` | `arrow.*`, `defaults.vector` | `CustomArrowTip` | — | px |

### 3.2. Обводка и заливка (имена, совместимые с SVG)

| Понятие | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | Аргумент manim | SVG |
|---|---|---|---|---|---|---|
| Цвет обводки | `<objColor r,g,b>` (зависит от типа) | `obj_color` | `stroke` | `color.*`, `import.colors`, `import.policy.stroke` | `color` | `stroke` |
| Непрозрачность обводки | `<lineStyle opacity>` | `line_opacity` | `stroke_opacity` | `import.colors` (с непрозрачностью), `import.policy.stroke_opacity` | `stroke_opacity` | `opacity` |
| Пунктир (соотношение) | `<lineStyle type>` (>0) | `line_type` | `stroke_dash_ratio` | `import.policy` (DSL) | `dashed_ratio=val, dash_length=0.17` | `stroke-dasharray` |
| Окончания линий | — | — | `stroke_linecap` | `rendering.line_cap` | `cap_style` | `stroke-linecap` |
| Цвет заливки | `<objColor>` (для angle/polygon/arc/conic/point) | `obj_color` | `fill` | `color.*`, `import.colors`, `import.policy.fill` | `fill_color` | `fill` |
| Непрозрачность заливки | `<objColor alpha>` | `obj_color['alpha']` / `obj_color['opacity']` | `fill_opacity` | `import.colors` (с целевой непрозрачностью), `import.policy.fill_opacity` | `fill_opacity` | `fill-opacity` |

### 3.3. Точки (форма и разложение пресета GGB)

`import.colors` нормализует результат в отдельные поля: в `stroke` и `fill`
попадает только hex `#rrggbb`, а `stroke_opacity` и `fill_opacity` меняются
только тогда, когда непрозрачность явно указана в правой части соответствия.
Например, `"#1565c0 0.1": "color.accent 1"` меняет цвет на `#f15b5b` и
выставляет непрозрачность `1.0`, а `"#1565c0 0.1": "color.accent"` сохраняет
прежнюю непрозрачность элемента.

| Понятие | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | Аргумент manim | SVG |
|---|---|---|---|---|---|---|
| Форма точки | `<pointStyle val="0..10">` (жёстко связана с заливкой) | `point_style` (int) | `point_shape` (строковый enum) | `import.policy.point_shape`, `overlay.per_type.point.point_shape` | `_make_point_mobject` (9 форм: circle, square, diamond, triangle_\*, cross, plus) | зависит от формы |

Код `point_style` из GGB раскладывается на три независимые оси (`point_shape`, `fill`/`fill_opacity`, `stroke`/`stroke_width_px`/`stroke_opacity`) через `style/enums.py:_GGB_POINT_STYLE_PATCHES`.

| `pointStyle` в GGB | `point_shape` | Заливка | Обводка |
|---|---|---|---|
| `0` (залитая, чёрный контур — по умолчанию) | `"circle"` | цвет | `#000000`, 1 px |
| `2` (полая окружность) | `"circle"` | нет (`fill_opacity=0`) | цвет, 2 px |
| `10` (залитая, без контура) | `"circle"` | цвет | нет (`stroke_opacity=0`) |
| `4` (залитый ромб) | `"diamond"` | цвет | нет |
| `5` (полый ромб) | `"diamond"` | нет | цвет, 2 px |
| `1` (×) | `"cross"` | нет | цвет, 2 px |
| `3` (+) | `"plus"` | нет | цвет, 2 px |
| `6`/`7`/`8`/`9` (▲/▼/▶/◀) | `"triangle_up"` / `"triangle_down"` / `"triangle_right"` / `"triangle_left"` | цвет | нет |

### 3.4. Углы

| Понятие | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim |
|---|---|---|---|---|---|
| Какую дугу рисовать | `<angleStyle val="1\|2">` | `angle_style` | `angle_range` (`"minor"` / `"reflex"`) | `import.policy.angle_range`, `overlay.per_name` | логика выбора в CreateMObject |
| Прямой угол (квадратный маркер) | автоматически | — | `right_angle_marker` (bool) | `overlay.per_name` | маркер `Polygon` вместо `AnnularSector` |
| Число дуг и засечек | `<decoration type>` | `decoration_lines` | `tick_count` (int) | `import.policy.tick_count`, `overlay.per_name` | цикл в CreateMObject |
| Стиль засечки (для Segment/Vector) | — | — | `tick_style` (`"line"` / `"wave"`) | `overlay.per_name` | `Line` против `round_corners_vmobject` |
| Толщина дуги | `<lineStyle thickness>` (как у линий) | `line_thickness` | `stroke_width_px` | `line_width.*`, `defaults.angle.stroke_width_px` | `stroke_width` |
| Соединение в прямом угле | — | — | `right_angle_joint` | `rendering.right_angle_joint`, `overlay.per_name` / `per_type` | `joint_type` у `VMobject` прямого угла |

### 3.5. Подписи

| Понятие | GGB XML | `elem.ggb_raw` | `elem.style` | JSON | manim |
|---|---|---|---|---|---|
| Текст | `<labelMode>`, `<caption>` | `label_caption` | `label_text` | `import.policy.label_text`, `overlay.per_name` | `Tex(text)` |
| Режим текста | `<labelMode val>` | `label_mode` (`0/1/2/3/9`) | `label_mode` (`label` / `value` / `label_value`) | `import.policy.label_mode`, `overlay.per_type`, `overlay.per_name` | выбирает `label`, `value` или `label = value` |
| Формат значения | — | — | `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator` | `overlay.per_type`, `overlay.per_name`, `import.policy.*` | форматирует числовую часть |
| Видимость | `<show label>` | `show_label` | `label_visible` | `defaults.<type>.label_visible`, `overlay.per_type`, `overlay.per_name`, `import.policy.label_visible` | (условное создание) |
| Цвет | `<objColor>` (тот же самый) | `obj_color.hex` | `label_color` | `import.policy.label_color` | `color` у `Tex` |
| Шрифт (размер) | `<gui><font size>` (на всю сцену) | — | `font_size_px` | `font_size.*`, `defaults.<type>.font_size_px`, `import.policy.font_size_px` | `font_size` |
| Якорь | `<labelingStyle>` (на всю сцену) | — | `label_anchor` (`"TL"`…`"BR"`) | `rendering.label_anchor`, `overlay.per_name` | `aligned_edge` в `move_to` |
| Смещение | `<labelOffset x,y>` | `label_offset_px` (Y инвертируется) | `label_offset_px` (после инверсии Y) | `import.policy.label_offset_px`, `overlay.per_name` | `tex.shift(...)` |
| Радиальное смещение (угол) | — | — | `label_radial_offset_px` | `overlay.per_name` | прибавляется к `r` для Angle |
| Зафиксированное положение | — | — | `label_placement_locked` (bool) | `overlay.per_name` | пропускается решателем |
| Внутренний флаг авторазмещения | — | — | `_auto_placed` (bool, внутренний) | — | отключает поправку на выносной элемент GGB в `create_label` |

### 3.6. Видимость и слои

| Понятие | GGB XML | `elem.ggb_raw` | elem.(style/атрибут) | JSON |
|---|---|---|---|---|
| Видимость элемента | `<show object>` | `show_object` | `elem.visible` (атрибут обёртки) / ключ resolver'а `visible` | `import.policy.visible`, `overlay.per_type`, `overlay.per_name`, `defaults.<type>.visible` |
| Z-index | — | — | `elem.style['z_index']` (float) | `rendering.polygon_boundary_layer`, `overlay.per_name` |
| Z-index заливки (CircleSector) | — | — | `elem.style['z_index_fill']` | `overlay.per_name` |

### 3.7. Полотно GeoGebra: сетка, оси, фон

Эти поля читаются из `<euclidianView>` в `geogebra.xml` и сохраняются в
`scene.style.export`, а не в `elem.ggb_style`: это настройки области
просмотра, а не свойства отдельных геометрических объектов.

| Понятие | GGB XML | `style.export` | Рендер |
|---|---|---|---|
| Размер области просмотра | `<size width height>` | `ptWidth`, `ptHeight` | размер камеры и SVG |
| Начало координат и масштаб | `<coordSystem xZero yZero scale yscale>` | `ptXZero`, `ptYZero`, `ptUnit`, `ptUnit_ggb`, `ptYUnit_ggb` | преобразование камеры, исходный вид |
| Показывать оси | `<evSettings axes>` | `showAxes` | включает оси в `_coordinate_background` |
| Показывать сетку | `<evSettings grid>` | `showGrid` | включает сетку в `_coordinate_background` |
| Жирная сетка | `<evSettings gridIsBold>` | `gridIsBold` | немного увеличивает толщину сетки |
| Тип сетки | `<evSettings gridType>` | `gridType` | сохраняется; пока отрисовывается декартова сетка |
| Цвет фона | `<bgColor r g b>` | `background` | сохраняется как hex |
| Цвет осей | `<axesColor r g b>` | `axesColor` | линии осей, засечки, числа |
| Цвет сетки | `<gridColor r g b>` | `gridColor` | линии сетки |
| Стиль линий | `<lineStyle axes grid>` | `axesLineStyle`, `gridLineStyle` | сохраняется для совместимости |
| Оси X и Y | `<axis id="0\|1" ...>` | `axes.x`, `axes.y` | по каждой оси: показ, числа, засечки |
| Шаг сетки | `<grid distX distY distTheta>` | `gridDistX`, `gridDistY`, `gridDistTheta` | `distX/distY` задают шаг сетки |

`_coordinate_background` рисуется до геометрии: сетка на `z_index=-20`, оси на
`z_index=-10`, засечки и числа на `z_index=-9`. Это не то же самое, что
встроенные `xAxis` и `yAxis` в `Construction`.

---

## Часть 4. Словарные перечисления (enum)

Определены в `animageo/style/enums.py` как типы `Literal` плюс кортеж времени выполнения для валидации.

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

## Часть 5. Единицы измерения и константы преобразования

### 5.1. Единицы

| Пространство | Единица | Где встречается |
|---|---|---|
| Экранные пиксели GGB | px | значения в GGB XML (pointSize, thickness, arcSize, labelOffset), `elem.ggb_raw`, суффикс `_px` в `elem.style` |
| Единицы JSON-стиля | пиксели (задаёт пользователь) | `presets`, `defaults.*` |
| Внутренние координатные единицы manim (MU) | 1 MU = `ptUnit` пикселей | радиусы, координатные длины, смещения |
| Единицы обводки и шрифта manim | шкала обводки и шрифта Manim | `stroke_width`, `set_stroke(width=...)`, `font_size` |
| Безразмерные | непрозрачность `[0..1]`, соотношение | `stroke_opacity`, `fill_opacity`, `stroke_dash_ratio` |
| Перечисления | строки | см. часть 4 |

**Контракт пиксельной инвариантности:** все значения `_px` хранятся в пикселях, но преобразуются в зависимости от целевого параметра Manim. Координатные размеры (`size_px`, `arc_size_px`, `tick_length_px`, `tick_shift_px`, `tick_radius_px`, `arrow_*_px`, смещения) переводятся в MU делением `/ ptUnit`. Толщины и шрифты, которые уходят в Manim через `stroke_width`, `set_stroke(width=...)` или `font_size`, проходят через масштаб рендера `* 100 / ptUnit`: это `stroke_width_px`, `tick_width_px`, `font_size_px`. Так гарантируется одинаковый визуальный результат при любом размере холста.

### 5.2. Константы (`animageo/constants.py`)

| Константа | Значение | Назначение |
|---|---|---|
| `STYLE_TO_INTERNAL` | `0.02` | внутренняя константа масштабирования; JSON-стиль времени выполнения использует `*_px` в пикселях |
| `LINE_WIDTH_SCALE` | `2` | внутренняя константа масштабирования толщины; рендерер читает `stroke_width_px` через resolver |
| `FONT_SIZE_RATIO` | `50/25.9 ≈ 1.93` | внутренняя константа масштабирования шрифта; рендерер читает `font_size_px` через resolver |
| `STROKE_WIDTH_SCALE` | `100` | `elem.style['stroke_width_px']` → `stroke_width` в manim (делится на `ptUnit`) |
| `GGB_FONT_SCALE` | `100.0` | пиксели шрифта GGB → `font_size` в manim (делится на `ptUnit`) |
| `Z_FILL`, `Z_FILL_INNER`, `Z_FILL_LABEL`, `Z_ANGLE`, `Z_LINE`, `Z_STROKE`, `Z_POINT`, `Z_LABEL` | уровни | z-index по типам элементов (значения по умолчанию) |

`builtin.json` (`animageo/style/builtin.json`) — поставляемые с пакетом значения по умолчанию по типам, в пикселях; `StyleConfig.load(user_path)` всегда начинает с него и подмешивает пользовательский JSON через `deep_merge`.

### 5.3. Примеры полной цепочки

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
    'label_offset_px': [-28, -32],  # Y инвертирован
    ...
}

↓ CreateMObject (во время рендера, ptUnit = 50)

Circle(radius=0.1, color='#000000', fill_color='#1565c0',
       fill_opacity=1, stroke_opacity=1, stroke_width=2)

↓ Cairo → SVG

<circle cx="…" cy="…" r="0.1"
        fill="#1565c0" fill-opacity="1"
        stroke="#000000" stroke-width="2"/>
```

**Пунктирная прямая из GGB** (`thickness=10`, `type=1`):
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

## История {#history}

Пересмотр имён полей вышел в **AnimaGeo 1.0.0** (2026-04-23) в рамках
переписывания геометрического ядра и системы стилей. Короткие и абстрактные
имена полей (`a`, `c`, `n`, `v`, `r`, `p`, `M`, `b`, `x`, `dim`, `angle`,
`original`, `points`, `end_points`, `start_point`) заменены понятными
человеку именами, описанными выше, **без псевдонимов для обратной
совместимости**: код, написанный под имена до версии 1.0 (`point.a`,
`circle.c`, `line.n`, `measure.x`, …), падает с `AttributeError` и должен
перейти на имена из части 1.

В JSON-формате обмена для анимации по ключевым кадрам используются те же
актуальные имена: `get_independents()` возвращает тип `'tparam_point'` и ключ
`'tparam'`; парсер ключевых кадров принимает только `'tparam'`.

Продолжение в **1.0.2**: удалён последний оставшийся псевдоним
`Construction.update_alpha` (для `update_tparam`), а вместе с ним — осиротевший
снимок заглушек для IDE, который всё ещё ссылался на имена полей до версии 1.0
(`Measure.x`, `Angle.angle`).

---

## См. также

- `docs/styles.md` — понятное человеку руководство по JSON-схеме с примерами.
- `animageo/style/enums.py` — исходный код со значениями enum и разложением GGB.
- `animageo/style/proxy.pyi` — полный список ключей `elem.style` с типовыми аннотациями для IDE.
- `animageo/style/schema.py` — docstring с каноническим примером JSON плюс валидатор.
