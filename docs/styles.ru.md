# Система стилей AnimaGeo — полный справочник

> Подробное руководство по всему визуальному слою AnimaGeo: JSON-схеме,
> ключам отдельных элементов, z-index, подписям и их автоматическому
> размещению, ImportPolicy, шрифтам, единицам, пиксельной инвариантности и
> различиям статического и анимированного вывода.

## Где читать о стилях

| Документ | Когда нужен |
|---|---|
| [Стили](styles.md) | Основной справочник: слои, JSON, resolver, единицы, overlay, рендер и импорт |
| [Архитектура](architecture.md) | Краткая карта прохождения GGB/DSL через `applyStyle`, `StyleConfig`, `ImportPolicy`, `StyleOverlay` и рендерер |
| [ImportPolicy](import_policies.md) | Только импорт и адаптация GGB: исходные значения → `elem.ggb_style`, директивы `scale:` / `quantize:` / `remap:` |
| [Поля объектов](field_names.md) | Соответствие GGB XML → `elem.ggb_raw` → `elem.ggb_style` / `elem.style` → JSON → рендерер |

## Идея слоёв

Стиль разделён по ответственности, а не по принципу «куда удобнее записать
ключ».

| Слой | Ответственность | Что здесь хранится | Чего здесь нет |
|---|---|---|---|
| `presets` | Семантические токены | Цвета, размеры, толщины, шрифты, пресеты засечек и стрелок | Правила выбора конкретных объектов |
| `defaults` | Базовый стиль по типу | «Все точки по умолчанию выглядят так» | Именованные исключения и GGB-remap |
| `import` | Адаптация GeoGebra | Карта цветов, точек и линий GGB; ImportPolicy | Стиль проекта по типу/имени |
| `overlay` | Правила поверх GGB и DSL | `per_type`, `per_name`, автоматические радиусы и подписи | Разбор исходных значений GGB |
| `reference` | Эталонный холст стиля | Ширина и высота для превью и масштабируемого экспорта | Физический размер файла |
| `rendering` | Общие параметры вывода | Окончания линий, фон, слои, показ точек | Стили отдельных объектов и GGB-remap |
| `elem.ggb_style` | Нормализованный импорт GGB | Адаптированные цвета, размеры, типы линий и подписи | Ручные изменения DSL/API |
| `elem.style` | Явные параметры элемента | Локальные изменения DSL/API | Общепроектные правила и исходные GGB-данные |

Короткое правило: **`import` отвечает, как читать GeoGebra; `overlay` — как
оформлять проект; `rendering` — как завершить и экспортировать рисунок.**

## Содержание

1. [Конвейер](#pipeline)
2. [Единицы и пиксельная инвариантность](#units)
3. [Холст, камера и экспорт](#canvas)
4. [JSON-схема](#schema)
5. [Z-index и слои](#z-index)
6. [Все ключи элемента](#element-style)
7. [Подписи и TeX](#labels)
8. [Автоматическое размещение подписей](#label-placement)
9. [ImportPolicy](#9-importpolicy)
10. [Статика и анимация](#static-animation)
11. [Ключевые кадры и интерполяция подписей](#keyframes-labels)
12. [Групповой API](#batch-api)
13. [Встроенные пресеты](#presets)
14. [Рецепты](#recipes)
15. [Особенности](#gotchas)
16. [Размеры и пропорции](#sizing)

## 1. Конвейер {#pipeline}

```text
.ggb → ggb_parser → Construction (Elements + ggb_raw + ggb_style)
                              │
                              ▼
             applyStyle(style=style.json, reference=..., content=..., export=...)
                              │
                              ├─ GeoStyle    — контекст экспорта сцены
                              ├─ StyleConfig — builtin.json + deep-merge JSON пользователя
                              │   ├─ presets
                              │   ├─ defaults.<type>
                              │   ├─ overlay.per_type / per_name
                              │   ├─ overlay.angle_radius
                              │   └─ overlay.label_placement
                              └─ ImportPolicy — raw GGB → elem.ggb_style
                              │
                              ▼  addAllGeometry
                   CreateMObject (Element → Manim Mobject)
                      └─ resolver.resolve(scene, elem, key)
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                  SVG       MP4      Live preview
```

Каждый элемент и сцена содержат несколько блоков:

| Источник | Когда заполняется | За что отвечает |
|---|---|---|
| `elem.ggb_raw` | `ggb_parser` | Исходные `point_size`, `line_thickness`, opacity/type, arc, label offset, `obj_color` |
| `elem.ggb_style` | parser + правила `applyStyle` + ImportPolicy | Нормализованная визуальная база GGB; используется, если `import.enabled != false` |
| `elem.style` | DSL/API, layout и keyframe helpers | Явные значения элемента с максимальным приоритетом |
| `scene.style_config` | `StyleConfig.load(style)` | `presets`, `defaults`, `overlay`, `rendering`, `reference` |
| `GeoStyle` | `applyStyle` | Контейнер палитры, флагов рендера и вычисленного `export` |

### Приоритет resolver

`resolver.resolve(scene, elem, key)` возвращает первое найденное значение:

```text
1. elem.style[key]                  — явная запись DSL/API
2. overlay.per_name[name][key]      — правило по имени
3. overlay.per_type[type][key]      — правило по типу
4. elem.ggb_style[key]              — импорт GGB, если он включён
5. defaults.by_type[type][key]      — builtin.json + defaults пользователя
6. внутренний стиль геометрического класса
7. default=… из аргумента вызова
```

`overlay` всегда сильнее импорта GGB, а `elem.style` сильнее всего. Overlay не
копируется в `elem.style`: рендерер читает его лениво через resolver.

### `builtin.json` и DSL

`animageo/style/builtin.json` всегда загружается первым, после чего JSON
пользователя накладывается через `deep_merge`. Поэтому достаточно короткого
файла:

```json
{"defaults": {"point": {"size_px": 10}}}
```

Все остальные базовые цвета, толщины и углы сохранятся. ImportPolicy работает
только с GGB, а общие правила для GGB и DSL должны находиться в
`overlay.per_type` / `overlay.per_name`.

## 2. Единицы и пиксельная инвариантность {#units}

В проекте сосуществуют три пространства единиц.

| Пространство | Где хранится | Примеры |
|---|---|---|
| **GGB px** | `ggb_raw`, `elem.ggb_style['*_px']`, `elem.style['*_px']` | Значения из `.ggb`, импорт и локальные стили |
| **Канонические style px** | `presets`, `defaults`, `overlay` | Все визуальные размеры JSON-стиля |
| **Внутренние / Manim** | Координаты и толщины итогового Mobject | То, что реально рисуется |

Преобразования собраны в `animageo/style/scaling.py`:

```python
# GGB px → elem.ggb_style
ggb_point_size_to_style(x)       = x * 2
ggb_thickness_to_stroke_width(x) = x / 2
ggb_arc_size_px(x, right=False)  = x  (или x/√2)
ggb_label_offset_to_style(x, y)  = [x, -y]

# resolved style → Manim во время рендера
stroke_width_to_manim(sw, ptUnit) = sw * 100 / ptUnit
ggb_font_px_to_manim_fontsize(px, ptUnit) = px * 100 / ptUnit
```

В канонической схеме размеры `presets`, `defaults.*` и `overlay.*` хранятся в
пикселях, а рендерер делит их на `ptUnit` ровно один раз.

### Контракт пиксельной инвариантности

Диаметр точки, толщина линии, шрифт, радиус дуги и смещение подписи хранятся в
пикселях. Рендерер делит их на `ptUnit_style`: стиль вычисляется относительно
эталонного холста и масштабируется вместе с ним до физического `export.size`.

`ptUnit_ggb` хранится отдельно — это исходное количество пикселей на единицу
GGB. Через него масштабируются подписи, чтобы на малом холсте они не
отрывались от геометрии.

Старые ключи `strich_len`, `strich_rshift`, `strich_width`, `arrow_height`,
`arrow_width`, `label_r_offset`, `line_width`, `ang_width`, `ang_rdefault`,
`ang_rshift`, `ang_right`, `font_size` больше не принимаются. Используйте
`tick_length_px`, `tick_shift_px`, `tick_width_px`, `arrow_length_px`,
`label_radial_offset_px`, `stroke_width_px`, `arc_size_px`, `arc_shift_px`,
`right_angle_size_px`, `font_size_px`.

## 3. Холст, камера и экспорт {#canvas}

Вычисленный `scene.style.export` содержит:

```python
scene.style.export = {
    'ptUnit': ..., 'ptWidth': ..., 'ptHeight': ...,
    'ptXZero': ..., 'ptYZero': ...,
    'ptUnit_style': ...,
    'referenceWidth': ..., 'referenceHeight': ...,
    'geometryScale': ..., 'exportScale': ...,
    'ptUnit_ggb': ..., 'fontSize': ...,
}
```

Современная раскладка разделяет три задачи:

```python
scene.loadGGB(
    'x.ggb',
    style='default',
    reference={'size': {'width': 300, 'height': 220}},
    content={'source': 'source_view', 'fit': 'contain'},
    export={'size': {'width': 1920, 'height': 1080}, 'fit': 'contain'},
)
```

- `reference` — эталонный холст, под который спроектирован стиль. Обычно
  хранится в JSON и при необходимости переопределяется во время выполнения.
- `content` — какую область конструкции помещать на эталон: `source_view`,
  `ggb_view` или `rendered_bounds`; также задаёт `fit`, `padding`, `anchor`,
  `offset`, `infinite_policy` и `prominence`.
- `export` — физический файл результата; runtime-параметр, который не хранится
  в JSON-стиле.
- `ptUnit_style` масштабирует все визуальные `*_px` относительно reference.
- `ptUnit` размещает итоговую картинку на холсте SVG/камеры.
- `geometryScale` — масштаб content/source rect до reference.
- `exportScale` / `contentScale` — увеличение reference до физического файла.
- `content.source='rendered_bounds'` сначала создаёт видимые Mobject в исходном
  масштабе, измеряет границы вместе с подписями и вписывает этот прямоугольник.
  `padding` добавляет поля. По умолчанию бесконечные `Line`/`Ray` игнорируются;
  `infinite_policy='clip'` измеряет их после обрезки камерой.

Неравномерное растяжение не поддерживается: используется единый `ptUnit`.

Reference можно сохранить в стиле:

```json
{
  "reference": {
    "size": {"width": 300, "height": 220},
    "source": "source_view"
  }
}
```

`reference.source` принимает `manual`, `source_view` или `ggb_view` и описывает
происхождение reference. Область конкретной конструкции выбирается через
`content.source`. Полный список параметров находится в [API](api.md).

Используйте `export={'size': {'width': w, 'height': h}}`; одна сторона может
быть равна `"auto"`. `px_size` больше не является основной публичной моделью.

## 4. JSON-схема {#schema}

Полное описание также находится в docstring `animageo/style/schema.py`.

```json
{
  "name": "необязательное имя",
  "version": 0.1,
  "presets": {
    "color": {
      "main": "#000000", "bold": "#000000", "aux": "#888888",
      "accent": "#f15b5b", "background": "#ffffff", "strong": "#000000"
    },
    "point_size": {"main": 2.83, "bold": 4.25, "aux": 2.12},
    "line_width": {"main": 1, "bold": 1.5, "aux": 0.75},
    "angle_radius": {"main": 17, "shift": 1.5, "right": 17},
    "tick": {"main": {"tick_length_px": 9, "tick_width_px": 1.5, "tick_shift_px": 2}},
    "arrow": {"main": {"arrow_length_px": 11, "arrow_width_px": 7.5}},
    "font_size": {"main": 14, "bold": 16, "aux": 12}
  },
  "defaults": {
    "point": {"size_px": "point_size.main", "fill": "color.strong"},
    "segment": {"$include": "tick.main", "stroke_width_px": "line_width.main"},
    "vector": {"$include": ["tick.main", "arrow.main"]}
  },
  "overlay": {
    "per_type": {"angle": {"arc_size_px": 22}, "point": {"size_px": 7}},
    "per_name": {"A": {"size_px": 99}},
    "angle_radius": {},
    "label_placement": {}
  },
  "rendering": {
    "background": "color.background",
    "line_cap": "butt",
    "right_angle_joint": "round",
    "polygon_boundary_layer": "top",
    "points_display": "auto",
    "label_anchor": "BL",
    "label_value_precision": 1
  },
  "import": {
    "colors": {"#1565c0": "color.main", "#d32f2f": "color.accent"},
    "point_size": {"5": "point_size.main"},
    "line_width": {"5": "line_width.main"},
    "policy": {}
  }
}
```

`overlay` — единственное публичное место для `per_type`, `per_name`,
`angle_radius` и `label_placement`. Он одинаково работает с GGB и DSL.

### Presets и defaults

`presets` — реестр именованных семантических констант. `main`, `bold`, `aux` —
лишь соглашение; можно добавить `construction`, `answer`, `hidden_helper` и
ссылаться на них как `"color.accent"` или `"line_width.bold"`.

| Группа | Назначение | Единицы |
|---|---|---|
| `color.*` | Именованные цвета | hex |
| `point_size.*` | Диаметр точек | style px |
| `line_width.*` | Толщина линий | style px |
| `angle_radius.*` | Радиусы и смещения углов | px |
| `tick.*` | `tick_length_px/tick_width_px/tick_shift_px` | px |
| `arrow.*` | `arrow_length_px/arrow_width_px` | px |
| `font_size.*` | Размер шрифта | px |

`defaults` хранит базу по типу: `defaults.point`, `defaults.segment`,
`defaults.angle` и т. д. Структурные пресеты подключаются через `$include`, а
локальные ключи блока типа имеют больший приоритет.

### Rendering

| Ключ | Значения | Эффект |
|---|---|---|
| `background` | hex или `color.*` | Фон камеры Manim/MP4 и viewport SVG |
| `line_cap` | `butt` / `round` / `square` | Окончания линий |
| `right_angle_joint` | `auto` / `bevel` / `miter` / `round` | Стык сторон маркера прямого угла |
| `polygon_boundary_layer` | `top` / `null` | `top`: контур многоугольника всегда над заливкой |
| `points_display` | `auto` / `only_labels` / `only_points` | Скрыть точки или подписи |
| `label_anchor` | `TL`…`BR` | Anchor подписи по умолчанию |
| `label_value_precision` | int | Точность подписей-значений |

Автоматические `overlay.label_placement` и `overlay.angle_radius` не
принимаются внутри `rendering`.

### Import

При `"enabled": false` геометрия и `elem.ggb_raw` сохраняются, но resolver
пропускает `elem.ggb_style`, карты цвета/размера и policy. База берётся из
`defaults`, а overlay и явные записи продолжают работать.

`colors` имеет формат `"#hex [opacity]" → "color.name|#hex [opacity]"`:

```json
"colors": {
  "#1565c0": "color.main",
  "#1565c0 0.1": "color.light 1",
  "#d32f2f": "color.accent",
  "#000000 0.6": "#2581b5"
}
```

Цвет записывается в `fill`/`stroke`, а opacity — только если явно указан
справа. Иначе текущая прозрачность сохраняется. `line_width` сопоставляет
толщины GGB с `line_width.*`, `point_size` делает то же для точек, а `policy`
описан в [ImportPolicy](import_policies.md).

### Сетка и оси GeoGebra

`loadGGB()` читает `<euclidianView>` и сохраняет фон координатной области в
`scene.style.export`.

| GGB XML | Поле | Назначение |
|---|---|---|
| `<evSettings axes>` | `showAxes` | Показ осей |
| `<evSettings grid>` | `showGrid` | Показ сетки |
| `<evSettings gridIsBold>` | `gridIsBold` | Более тяжёлые линии сетки |
| `<evSettings gridType>` | `gridType` | Пока хранится; рисуется декартова сетка |
| `<axesColor>` / `<gridColor>` | `axesColor` / `gridColor` | Цвета осей и сетки |
| `<grid distX distY distTheta>` | `gridDistX/Y/Theta` | Шаг сетки |
| `<axis id show>` | `axes.x/y.show` | Видимость отдельной оси |
| `<axis showNumbers>` | `axes.x/y.showNumbers` | Числовые подписи |
| `<axis tickDistance>` | `axes.x/y.tickDistance` | Шаг засечек |

`addAllGeometry()` добавляет `_coordinate_background` перед геометрией: сетка
имеет `z_index=-20`, оси — `-10`, числа и засечки — `-9`. Это фон, а не
служебные элементы `xAxis` / `yAxis` из Construction.

## 5. Z-index и слои {#z-index}

```text
Z_POINT      = 50      точки — верхний слой
Z_LABEL      = 50      подписи над обводками
Z_STROKE     = 5       отрезки, засечки, контуры дуг
Z_LINE       = 4       прямые и окружности
Z_ANGLE      = 3       дуги углов
Z_FILL_LABEL = 0.1     подписи на уровне заливок
Z_FILL       = 0.01    заливки многоугольников и секторов
Z_FILL_INNER = 0.001   зарезервированный нижний слой заливки
```

При `z_auto=True` слой назначается по типу. Точки и обычные подписи получают
50; сегменты, окружности, дуги и векторы — 5; углы — 3; многоугольники и
секторы — 0.01, их подписи — 0.1. Контур многоугольника всегда выше заливки;
при `polygon_boundary_layer="top"` стороны получают `z_index=10`.

Для стабильности MP4 к реальному Manim `z_index` добавляется микросмещение
`construction_index × 1e-6`. Оно не меняет уровни, но делает порядок внутри
уровня детерминированным после пересоздания Polygon.

Явное значение отключает автоматическое:

```python
scene.element('poly').style['z_index'] = 100
scene.element('sector').style['z_index_fill'] = 0.2
```

## 6. Все ключи элемента {#element-style}

`elem.style` — обычный изменяемый Python-словарь.

### Видимость и обводка

| Ключ | Тип | По умолчанию / смысл |
|---|---|---|
| `elem.visible` | bool | Атрибут; полностью скрывает Mobject |
| `visible` | bool | `True`; GGB Show object через resolver |
| `label_visible` | bool | Зависит от элемента; рисовать подпись |
| `stroke` | hex | `style.strong` |
| `stroke_width_px` | float px | `defaults.<type>.stroke_width_px` |
| `stroke_opacity` | 0..1 | `1` |
| `stroke_dash_ratio` | 0..1 / None | Сплошная линия при None |
| `stroke_linecap` | `butt` / `round` / `square` / `auto` | `rendering.line_cap` |
| `right_angle_joint` | `auto` / `bevel` / `miter` / `round` | `rendering.right_angle_joint` |

### Заливка и точки

| Ключ | Тип | Значение |
|---|---|---|
| `fill` | hex | Цвет заливки; для точек обычно `style.strong` |
| `fill_opacity` | 0..1 | `1` |
| `size_px` | float px | Диаметр точки |
| `point_shape` | enum | `circle`, `square`, `diamond`, `triangle_up/down/left/right`, `cross`, `plus` |

### Углы

| Ключ | Тип | Эффект |
|---|---|---|
| `arc_size_px` | float px | Базовый радиус дуги |
| `arc_shift_px` | float px | Шаг между несколькими дугами |
| `angle_range` | `minor` / `reflex` | Меньший или рефлексный сектор |
| `right_angle_marker` | bool | Принудительно включить/выключить квадрат |
| `right_angle_size_px` | float px | Размер квадрата прямого угла |
| `tick_count` | int | Количество дуг |

### Отрезки и векторы

| Ключ | Тип | Эффект |
|---|---|---|
| `tick_count` | int | Количество засечек в середине |
| `tick_style` | `line` / `wave` | Прямая или волнистая засечка |
| `tick_radius_px` | float | Радиус скругления wave, по умолчанию `tick_shift_px * 0.45` |

### Подписи

| Ключ | Тип | По умолчанию / эффект |
|---|---|---|
| `label_text` | TeX | `"$" + elem.name + "$"` |
| `label_mode` | `label` / `value` / `label_value` | Имя, вычисленное значение или `имя = значение` |
| `label_value_precision` | int | `1` знак после запятой |
| `label_value_strip_zeros` | bool | Удалять нули: `5.00 → 5` |
| `label_angle_unit` | `degree` / `radian` | Единицы угла |
| `label_value_separator` | str | `" = "` |
| `label_color` | hex | Цвет текста |
| `label_anchor` | `TL`…`BR` | Какая точка bbox попадает в anchor |
| `label_offset_px` | `[x, y]` | Смещение, делится на `ptUnit_ggb` |
| `font_size_px` | float px | Шрифт элемента |
| `label_radial_offset_px` | float px | Радиальное смещение, обычно для углов |
| `label_placement_locked` | bool | Защитить от auto-placement |
| `_auto_placed` | bool | Внутренний флаг; отключает GGB descender correction |
| `z_index` / `z_index_fill` | float | Явный слой элемента/заливки |

## 7. Подписи и TeX {#labels}

Anchor выбирается по сетке из девяти точек:

```text
TL ── TC ── TR
│     MC     │
ML          MR
│            │
BL ── BC ── BR
```

Он задаётся через `elem.style['label_anchor']` или глобальный
`rendering.label_anchor`. `MC` центрирует подпись на точке; GeoGebra по
умолчанию использует `BL`.

`animageo/ui.py::RusTex` использует `pdflatex`, `T2A`, `babel russian`, UTF-8,
настроенные дроби, уменьшенные `\angle` и `\triangle`.

`correctedLabel(label)` выполняет 84 замены Unicode → TeX, например
`· → \cdot`, `α → \alpha`, `△ → \triangle`.

GGB привязывает offset к низу поля ввода вместе с descender padding, а TeX bbox
плотный. Поэтому `create_label` автоматически поднимает подпись на
`ggb_font_px * 0.25 / ptUnit`, кроме случая `_auto_placed=True`.

## 8. Автоматическое размещение подписей {#label-placement}

Есть три режима: одноразовый статический, снимки ключевых кадров и tracker на
каждом кадре.

```python
scene.loadGGB('x.ggb', style='default',
              export={'size': {'width': 800, 'height': 600}})
scene.autoPlaceLabels()
scene.exportSVG('out.svg')
```

Жадный solver проверяет восемь направлений E/NE/N/NW/W/SW/S/SE, минимизирует
перекрытия и сначала размещает наиболее ограниченные подписи.

| Ключ `overlay.label_placement` | Default | Описание |
|---|---:|---|
| `enabled` | `false` | Автоматически вызвать `autoPlaceLabels()` после `loadGGB` |
| `distance_px` | `6` | Базовое расстояние anchor → центр подписи |
| `padding_px` | `2` | Поле bbox при проверке пересечений |
| `angle_gap_arc_px` | `3` | Зазор от внешней дуги угла |
| `angle_gap_sides_px` | `3` | Зазор от сторон узкого угла |
| `w_anchor` | `1.0` | Штраф за отклонение от предпочитаемого направления |
| `w_label` | `10.0` | Вес пересечения подпись×подпись |
| `w_geom` | `8.0` | Вес пересечения подпись×геометрия |
| `dynamic_angles` | `false` | Пересчитывать биссектрисы по кадрам |
| `keyframe_snapshots` | `false` | Рассчитать layout на ключевых кадрах и интерполировать |
| `canonicalize_anchor` | `false` | Перевести anchor в `MC` с компенсацией; может сдвинуть старый результат |
| `interpolation` | `linear` | `linear` или `smooth` между снимками |
| `ema_alpha` | `0.2` | Вес свежего решения solver; меньше = плавнее |
| `anchor_flip_frames` | `6` | Сколько кадров подряд нужен новый anchor |
| `solver_every_n_frames` | `2` | Запуск solver раз в N кадров |

### Углы

Подпись угла всегда лежит на биссектрисе:

```text
dist = arc_radius_effective + max(half_w, half_h) + gap_arc
dist ≥ (√(hw² + hh²) + gap_sides) / sin(half_angle)  # для узких углов
```

При `tick_count=N` внешний радиус равен
`arc_size_px + (N - 1) * arc_shift_px`, поэтому подпись не попадает на крайнюю
дугу. Anchor всегда `MC`.

Ручная блокировка:

```python
scene.element('A').style['label_placement_locked'] = True
scene.element('A').style['label_offset_px'] = [10, -5]
```

### Автоматический радиус угла

Для узкого угла фиксированная дуга может исчезнуть между сторонами. При
`overlay.angle_radius.enabled=true` радиус умножается на
`(pivot / angle) ** exp` и ограничивается диапазоном от `min_px` до
`max_arm_fraction · min(|v1|, |v2|) · ptUnit`.

| Ключ | Default | Значение |
|---|---:|---|
| `enabled` | `false` | Явное включение, чтобы обычный импорт оставался точным |
| `exp` | `0.25` | Степень масштабирования; `0` отключает его |
| `pivot_rad` | `π/2` | Угол, при котором масштаб равен 1 |
| `min_px` | `12` | Нижняя граница радиуса |
| `max_arm_fraction` | `0.65` | Максимальная доля короткой стороны |
| `apply_to_right` | `false` | Применять ограничения к маркеру прямого угла |

Для одного угла `elem.style['auto_radius'] = False` фиксирует `arc_size_px`.
Подпись использует тот же `compute_effective_arc_size_px` и остаётся за внешней
дугой.

```json
"overlay": {
  "angle_radius": {
    "enabled": true, "exp": 0.3, "min_px": 14,
    "max_arm_fraction": 0.55
  }
}
```

## 9. ImportPolicy

ImportPolicy преобразует `.ggb` в `elem.ggb_style`. Приоритет: `faithful()` →
`import.policy` JSON → аргумент `loadGGB(..., import_policy=...)` →
`setElementStyle()` после загрузки.

Поля принимают `None`, литерал, Python-функцию `fn(raw, defaults, elem)` или
строковую директиву. Основные соответствия:

| Поле | Источник GGB | Ключ результата |
|---|---|---|
| `size_px` | `<pointSize>` | `size_px` |
| `stroke_width_px` | `<lineStyle thickness>` | `stroke_width_px` |
| `arc_size_px` | `<arcSize>` | `arc_size_px` |
| `label_offset_px` | `<labelOffset>` | `label_offset_px` |
| `label_color`, `stroke`, `fill` | `obj_color.hex` | одноимённый ключ |
| `fill_opacity` | `obj_color.opacity` | `fill_opacity` |
| `visible`, `label_visible`, `label_text` | `<show>` / `<caption>` | одноимённый ключ |
| `angle_range`, `tick_count`, `point_shape` | angle/decoration/point style | одноимённый ключ |
| `stroke_opacity`, `stroke_dash_ratio`, `stroke_linecap` | line style / literal | одноимённый ключ |

Мини-DSL: `const:3`, `scale:1.5`, `quantize:[1,2,4]`,
`remap:{'#f00':'#c00'}`, `match_element`, `auto`. Полное описание и рецепты —
в [ImportPolicy](import_policies.md).

Политику можно заменить без повторного чтения XML:

```python
scene.reloadPolicy(ImportPolicy(size_px=5))
```

## 10. Статика и анимация {#static-animation}

| Аспект | SVG | MP4 |
|---|---|---|
| Подписи | Одноразовый `autoPlaceLabels()` | Снимки и интерполяция либо tracker |
| Углы | Биссектриса вычисляется один раз | `dynamic_angles` пересчитывает каждый кадр |
| Z-index | Читается при экспорте | Переназначается при update, равные уровни стабилизируются индексом |
| `stroke_linecap` | Видим | Видим; `butt` резкий, `round` плавный |
| Шрифт | GGB descender correction | То же, но `_auto_placed=True` отключает коррекцию |
| `ptUnit` | Фиксируется после `applyStyle` | Не меняется при движении камеры |

Для MP4 Manim использует `config.pixel_width/pixel_height`, а не
`style.export.ptWidth`. Потребитель должен явно согласовать Manim config с
`export["size"]`. Библиотека не выбирает качество, bitrate и FPS за приложение.

## 11. Ключевые кадры и интерполяция подписей {#keyframes-labels}

```json
{
  "keyframes": [
    {"t": 0, "values": {"A": [0, 0], "x": 35, "D": {"tparam": 0.0}}},
    {"t": 2, "values": {"A": [4, 4], "x": 110,
      "D": {"tparam": 3.14, "direction": "ccw"}},
      "show": ["line1"], "hide": ["aux"], "easing": "smooth"},
    {"t": 4, "values": {"A": [0, 0], "x": 35}}
  ]
}
```

Свободная точка принимает `[x,y]`; точка на окружности — `tparam` и
`short/cw/ccw`; точка на отрезке — `tparam` от 0 до 1; числа и углы
интерполируются линейно; boolean переключается в середине.

Для интеграции auto-placement:

```json
"overlay": {
  "label_placement": {
    "keyframe_snapshots": true,
    "dynamic_angles": true,
    "canonicalize_anchor": true,
    "interpolation": "smooth"
  }
}
```

`keyframe_snapshots` рассчитывает layout каждого ключевого кадра с сохранением
и восстановлением состояния. `dynamic_angles` обновляет биссектрисы,
`canonicalize_anchor` переводит anchor в `MC` и устраняет дискретные скачки.
Сам по себе `dynamic_angles` намеренно ничего не делает.

Tracker для обычного `addUpdater`:

```python
x = scene.addVar('x', 0)
scene.autoPlaceLabels(dynamic=True)
with scene.animating(x):
    scene.play(x.animate.set_value(1), run_time=3)
scene.clearLabelTracker()
```

EMA через `ema_alpha` и гистерезис `anchor_flip_frames` подавляют дрожание.

## 12. Групповой API {#batch-api}

```python
scene.setElementStyle(
    ['a', 'b', 'c'],
    stroke='#ff0000', stroke_width=3, fill_opacity=0.5,
)
scene.setVisible(['A', 'B', 'C'], False)
```

`setElementStyle` записывает пары в `elem.style`. Контекстный менеджер
`animating` эквивалентен `addUpdater` → `try/play/clearUpdater`.

| Метод | Действие |
|---|---|
| `Show` / `playShow` | Показать через Fade/Create |
| `Hide` / `playHide` | Скрыть |
| `Shade` / `playShade` | Приглушить через `col_shade` |
| `Restore` / `playRestore` | Восстановить после Shade |
| `Update` / `playUpdate` | FadeOut → пересоздать → FadeIn |
| `UpdateAll()` | То же для всей сцены |
| `ShowCreate(name)` | Create для линий, Fade для заливок и углов |

## 13. Встроенные пресеты {#presets}

В `animageo/style/presets/` находятся пять стилей. Передайте короткое имя в
`style=`; локальный файл с тем же именем имеет приоритет.

```text
default        синяя/красная базовая палитра
book_blue      печатный синий
book_green     печатный зелёный
book_purple    печатный фиолетовый
book_red       печатный красный с синим акцентом
```

```python
scene.loadGGB('x.ggb', style='book_green')
```

Текущий список возвращает `available_style_presets()` из
`animageo.style.config`.

## 14. Рецепты {#recipes}

### Единые подписи, точки и толщины

```python
ImportPolicy(font_size_px=14, label_color='#222222')
ImportPolicy(size_px=3)
ImportPolicy(stroke_width_px='quantize:[1, 2, 4]')
```

### Замена палитры

```json
"import": {
  "colors": {
    "#1565c0": "color.main",
    "#d32f2f": "color.accent"
  }
}
```

Или `ImportPolicy(stroke="remap:{'#1565c0':'#0066cc'}")`.

### Двойная дуга и высокий многоугольник

```python
scene.element('α').style['tick_count'] = 2
scene.element('α').style['arc_shift_px'] = 3
scene.element('poly').style['z_index'] = 100
```

### Масштабируемый экспорт 2×

```python
scene.loadGGB(
    'x.ggb', style='default',
    reference={'size': {'width': 800, 'height': 600}},
    export={'size': {'width': 1600, 'height': 1200}},
)
```

Геометрия и визуальные `*_px` масштабируются вдвое относительно reference.

### Волнистые засечки и подпись над точкой

```python
scene.element('a').style['tick_count'] = 2
scene.element('a').style['tick_style'] = 'wave'
scene.element('a').style['tick_radius_px'] = 1.5

scene.element('A').style['label_anchor'] = 'BC'
scene.element('A').style['label_offset_px'] = [0, 10]
```

Для схемы только с буквами: `"rendering": {"points_display": "only_labels"}`.

## 15. Особенности {#gotchas}

1. `dynamic_angles=true` требует `keyframe_snapshots=true` или
   `autoPlaceLabels(dynamic=True)`.
2. `canonicalize_anchor=true` переписывает записанные anchor и может сдвинуть
   существующий результат.
3. Кэш TeX bbox общий для процесса и имеет ключ `(label_text, font_size)`.
   После ручного изменения RusTex вызовите `clear_bbox_cache()`.
4. `Polygon.become()` в Manim работает некорректно, поэтому
   `updateGeoElements` использует remove+add, а порядок стабилизируется
   микросмещением z-index.
5. Updater анимированного ValueTracker видит только начало и конец; поэтому
   `play_keyframes` использует sentinel Mobject.
6. У DSL-элементов `elem.ggb_raw` пуст, и ImportPolicy получает `raw=None`.
7. Автоопределение прямого угла через `np.isclose` может сработать около
   89,5°–91°; при важной точности задайте `right_angle_marker` явно.
8. `arc_size_px` имеет приоритет над `r_offset`.
9. Удалённые `line_width`, `font_size`, `strich_*`, `arrow_*`,
   `label_r_offset`, `ang_*` отклоняются; используйте канонические `*_px`.

## 16. Размеры и пропорции {#sizing}

Все `*_px` не зависят от физического разрешения. Важны отношения семейств и
их размер относительно reference. Для холста около **800×600** подходят:

| Семейство | `main` | `bold` | `aux` | Ориентир |
|---|---:|---:|---:|---|
| `line_width` | 1.5–2 | 2.5–3.3 | 0.75–1.5 | базовая единица |
| `point_size` — диаметр | 6–8 | 9–10 | 4–5 | 3.5–4.5 × толщина линии |
| `font_size` | 14–17 | 16–20 | 12–14 | 2–2.5 × диаметр точки |
| `angle_radius` | 17–20 | 24 | 12 | 1–1.2 × шрифт; right ≈ 0.8–0.9 × main |
| `tick_length_px` | 9–10 | — | — | 5–6 × толщина линии |
| `arrow_length_px` | 10–11 | — | — | 6–7 × толщина линии |

Диаметр точки — примерно 1% ширины холста, подпись — 2,5–3% высоты. Типичные
ошибки: огромные точки на тонких линиях, дуги больше коротких сторон, слишком
громкие подписи и засечки короче пяти толщин линии.

### Масштаб холста

1. Предпочтителен reference 700–1000 px; увеличивайте физический `export.size`
   без изменения стиля.
2. При переходе на другой класс reference масштабируйте все px-семейства одним
   коэффициентом по отношению диагоналей.
3. Для 16:9 подходит reference 960×540; существующий пресет можно оставить или
   увеличить px-семейства примерно на 1.1.
4. Мелкая геометрия с крупными точками — обычно проблема кадрирования. Сначала
   исправьте fit и заполнение 70–85%, а не размеры декораций.

### Один регулятор: `prominence`

`content={'prominence': k}` одновременно умножает размеры точек, линий,
шрифтов, дуг и засечек, не меняя геометрию, crop и отношения:

```python
scene.applyStyle(
    reference={'size': {'width': 800, 'height': 600}},
    content={
        'source': 'rendered_bounds', 'padding': 40,
        'prominence': 1.25,
    },
    export={'size': {'width': 800, 'height': 600}},
)
```

`content.decoration_scale_source` задаёт опору плотности декораций: `frame` —
по crop, по умолчанию; `reference` — постоянная доля geometry/reference;
`output` — постоянный размер в пикселях результата; `ggb` — пропорции апплета.

Для плотной фигуры уменьшите систему точек/подписей до `aux`, включите
`label_placement` и дайте геометрии больше места. Для редкой демонстрационной
фигуры на слайде используйте `prominence=1.2–1.4`. Соседние дуги углов у одной
вершины разделяйте шагом `arc_size_px` 6–10 px.

## См. также

- [API](api.md)
- [ImportPolicy](import_policies.md)
- [Особенности и ошибки](gotchas.md)
- [Архитектура](architecture.md)
- `animageo/style/schema.py`
- `animageo/style/scaling.py`
