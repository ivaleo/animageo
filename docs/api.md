# Справочник API

## AnimaGeoScene

Основной класс --- наследник `manim.MovingCameraScene`.

### Загрузка данных

| Метод | Описание |
|-------|----------|
| `loadGGB(filepath, style=None, import_policy=None, debug=False, generate_stubs=True, strict=False, reference=None, content=None, export=None)` | Загрузить .ggb файл, применить стиль (опционально через `ImportPolicy`), отобразить геометрию. `style` принимает путь, dict или `StyleConfig`; `reference` задает эталонный холст; `content` размещает конструкцию на нем; `export` задает физический вывод. Unsupported GGB-команды в non-strict режиме попадают в `scene.geo.command_diagnostics` без cascade warning-шума; `strict=True` превращает root unsupported в ошибку. `generate_stubs=True` пишет `<basename>_stubs.pyi` рядом с .ggb |
| `loadCode(filepath, debug=False, show=True)` | Загрузить Python-файл с DSL-кодом (exec-движок) |
| `putCode(code, debug=False, show=True)` | Выполнить строку Python-кода как DSL (exec-движок; см. [docs/python_dsl.md](python_dsl.md)) |
| `applyStyle(style=None, import_policy=None, reference=None, content=None, export=None)` | Применить стиль к текущей конструкции и пересчитать layout. Внутри: builtin + `style`, затем `reference -> content -> export` |
| `fitView(width=800, height=600, *, padding=40, style=None, passes=2)` | Канонический фрейминг DSL-сцены: измеряет rendered bounds видимых элементов и укладывает их на холст `width×height` с полем `padding` px. Делает `passes` раундов `applyStyle(content='rendered_bounds')` + `updateAllGeometry()` (первый раунд выставляет масштаб пиксельных стилей, второй пере-меряет с уже правильными размерами точек/подписей). Без `style=` сохраняет текущий `style_config` сцены. Вызывать, пока нужные элементы видимы (до `HideAll()`); для анимаций закладывать запас `padding` под движение |
| `applyOverlay()` | Совместимый no-op hook. Overlay больше не пишется в элементы; resolver читает `style_config.overlay.per_type` / `per_name` лениво |
| `reloadPolicy(import_policy)` | Применить новую `ImportPolicy` без повторного парсинга XML (использует закешированные `elem.ggb_raw`). Действует только на GGB-элементы |

Политика импорта — см. раздел `ImportPolicy` ниже и [docs/import_policies.md](import_policies.md).

Unsupported-команды GeoGebra диагностируются структурированно:

```python
scene.loadGGB('scene.ggb', strict=False)
scene.geo.command_diagnostics
# [{'command': 'Sub', 'signature': ['str', 'AngleSize'],
#   'outputs': ['_3'], 'reason': 'unsupported_signature'}]
```

Команды, которые получили `None` только из-за такого root unsupported, добавляются
как `dependents` к исходному diagnostic и не логируются пачкой как независимые
проблемы.

### Параметры layout: `style`, `reference`, `content`, `export`

`loadGGB(...)` и `applyStyle(...)` используют один и тот же pipeline:
`style/reference -> content -> export`.

`style` задает визуальный стиль:

| Значение | Поведение |
|---|---|
| `None` | builtin-стиль без пользовательского JSON |
| `str` / `PathLike` | путь к style JSON; грузится поверх builtin |
| `dict` | style JSON передается напрямую |
| `StyleConfig` | готовая конфигурация; используется ее `source` для совместимого `GeoStyle` и сама конфигурация для resolver |

`reference` задает эталонный холст, на котором стиль считается авторским:

| Поле | Значения | Дефолт / смысл |
|---|---|---|
| `size` | `[width, height]` или `{"width": w, "height": h}`; каждая сторона — положительное число, `None` или `"auto"` | runtime override над `style.reference.size`; если не задано, берется исходный viewport конструкции |
| `source` | `"manual"`, `"source_view"`, `"ggb_view"` | metadata в style JSON: откуда взят эталон. Саму область конструкции выбирает `content.source` |

`content` описывает, какую область конструкции уложить в `reference`:

| Поле | Значения | Дефолт / смысл |
|---|---|---|
| `source` | `"source_view"`, `"ggb_view"`, `"rendered_bounds"`; aliases: `"ggb"` -> `"ggb_view"`, `"bounds"` -> `"rendered_bounds"` | `"source_view"` |
| `fit` | `"contain"`, `"cover"`, `"width"`, `"height"`, `"none"`, `"manual"` | `"contain"` |
| `scale` | положительное число | только для `fit="manual"`; alias `manual_scale` |
| `anchor` | `"top_left"`, `"top"`, `"top_right"`, `"left"`, `"center"`, `"right"`, `"bottom_left"`, `"bottom"`, `"bottom_right"` | `"center"` |
| `offset` | `[x, y]` в пикселях | дополнительный сдвиг после anchor |
| `padding` | число >= 0 | отступ в source-пикселях для `source="rendered_bounds"`; alias `bounds_padding` |
| `infinite_policy` | `"ignore"` или `"clip"` | `"ignore"`: `Line`/`Ray` не расширяют measured bounds; `"clip"`: они измеряются после обрезки текущей source-камерой |

`export` описывает физический выходной холст:

| Поле | Значения | Дефолт / смысл |
|---|---|---|
| `size` | `[width, height]` или `{"width": w, "height": h}`; одна сторона может быть `None`/`"auto"` | если не задано, размер равен `reference.size`; `[auto, auto]` недопустим |
| `fit` | `"contain"`, `"cover"`, `"width"`, `"height"`, `"none"`, `"manual"` | `"contain"` |
| `scale` | положительное число | только для `fit="manual"`; alias `manual_scale` |
| `anchor` | те же 9 anchor-значений, что у `content.anchor` | `"center"` |
| `offset` | `[x, y]` в пикселях | сдвиг reference-картинки внутри export-холста |

При загрузке `.ggb` parser также переносит параметры `<euclidianView>` в
`style.export`: `showAxes`, `showGrid`, `gridIsBold`, `gridType`,
`axesColor`, `gridColor`, `gridDistX`, `gridDistY`, `gridDistTheta`,
`axes.x` и `axes.y`. `addAllGeometry()` использует их для фонового слоя
`_coordinate_background`: сетка рисуется под геометрией, оси и деления — над
сеткой, но ниже всех объектов конструкции.

### Переменные и обновление

| Метод | Описание |
|-------|----------|
| `addVar(name, value)` | Создать анимируемую переменную, вернуть ValueTracker |
| `addUpdater(tracker)` | Привязать ValueTracker к перестроению геометрии |
| `clearUpdater(tracker)` | Отвязать ValueTracker |
| `animating(tracker)` | Контекстный менеджер: addUpdater + yield + clearUpdater |
| `updateAllGeometry()` | Перестроить все manim-объекты по текущей геометрии |

Пример `animating`:
```python
x = self.addVar('x', 0)
with self.animating(x):
    self.play(x.animate.set_value(1), run_time=3)
```

### Анимации

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `Show(names, mode)` | `[Animation]` | Показать элементы. mode: `'Fade'` или `'Create'` |
| `Hide(names)` | `[Animation]` | Скрыть элементы |
| `Shade(names)` | `[Animation]` | Затенить элементы (серый цвет) |
| `Restore(names)` | `[Animation]` | Восстановить из затенения |
| `Update(names)` | `[Animation]` | Перерисовать элементы |
| `UpdateAll()` | `[Animation]` | Перерисовать все элементы |

Удобные обёртки с автозапуском `self.play(...)`:

```python
self.playShow(['A', 'B', 'C'])
self.playHide(['A'])
self.playShade(['B', 'C'])
self.playRestore(['B', 'C'])
self.playUpdate(['a', 'b'])
```

### Keyframe-анимации

| Метод | Описание |
|-------|----------|
| `get_independent_elements()` | Вернуть анимируемые входы конструкции для `values`: свободные точки, точки на путях, числа/углы/booleans и переменные, созданные через `addVar()` |
| `get_element_states()` | Вернуть `{name: {type, visible, style}}` для всех не-осевых элементов: текущая видимость и resolved animatable style values; удобно для UI keyframe-state inspector |
| `play_keyframes(keyframes_data)` | Воспроизвести JSON/dict timeline. `"version": 2` включает style tracks, visibility/effects, camera keyframes и events; v1 без `version` оставлен для совместимости и deprecated |
| `apply_keyframes_at(keyframes_data, t)` | Статически применить состояние timeline в момент `t` без `self.play(...)`; полезно для SVG/PNG preview одного кадра |
| `reveal_construction(lag=0.3, duration=0.5, effect=None, play=True)` | Сгенерировать v2 timeline появления элементов в dependency order и сразу проиграть его; при `play=False` вернуть timeline dict |

Короткий пример:

```python
self.play_keyframes({
    "version": 2,
    "keyframes": [
        {"t": 0, "values": {"A": [0, 0]}, "visible": {"a": False}},
        {"t": 2, "values": {"A": [4, 2]},
         "styles": {"a": {"stroke": "#d05456", "stroke_width_px": 4}},
         "visible": {"a": True},
         "enter": {"a": "create"},
         "events": [{"effect": "indicate", "targets": ["A"], "at": 0.4, "duration": 0.6}]},
    ],
})
```

Полный формат: [docs/keyframes.md](keyframes.md).

### Пакетные операции

| Метод | Описание |
|-------|----------|
| `setElementStyle(names, **props)` | Установить стиль на нескольких элементах сразу |
| `setVisible(names, visible)` | Установить видимость нескольких элементов |

```python
self.setElementStyle(['a', 'b', 'c'], stroke='#ff0000', fill_opacity=0.5)
self.setVisible(['A', 'B', 'C', 'D', 'E'], False)
```

### Доступ к данным

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `element(name)` | `Element` | Элемент конструкции по имени |
| `mobject(name)` | `Mobject` | Manim-объект по имени |

### Расстановка подписей

| Метод | Описание |
|-------|----------|
| `autoPlaceLabels(dynamic=False)` | Автоматически разложить подписи. `dynamic=True` устанавливает `LabelTracker` — последующие `addUpdater(...)` анимации будут пересчитывать раскладку на каждом кадре с EMA-сглаживанием и гистерезисом якоря |
| `clearLabelTracker()` | Снять `LabelTracker`. Дальнейшие `updateVar` не будут дёргать per-frame решатель |

Статический вызов (легаси, one-shot — как было):

```python
scene.loadGGB(
    'scene.ggb',
    style='style.json',
    export={'size': {'width': 800, 'height': 600}},
)
scene.autoPlaceLabels()
scene.exportSVG('out.svg')
```

Динамическая раскладка под `addUpdater`:

```python
scene.loadGGB(
    'scene.ggb',
    style='style.json',
    export={'size': {'width': 800, 'height': 600}},
)
x = scene.addVar('x', 0)
scene.autoPlaceLabels(dynamic=True)   # ставит LabelTracker
scene.addUpdater(x)
scene.play(x.animate.set_value(1), run_time=3)
# Углы следят за биссектрисой per-frame, остальные подписи плавно подтягиваются
# к решателю через EMA. При canonicalize_anchor=True все якоря — 'MC', без прыжков.
scene.clearUpdater(x)
scene.clearLabelTracker()
```

Конфигурация — `overlay.label_placement` в JSON стиля (см. [docs/styles.md](styles.md)).

`play_keyframes()` перед стартом playback применяет значения, v2 `visible` и
legacy `show`/`hide` из первого keyframe, перестраивает геометрию и обновляет
mobject-ы. Поэтому первый rendered frame соответствует keyframe `0`, даже если
сохраненный `.ggb` был в другом editor-state. При `keyframe_snapshots=true`
раскладка считается на каждом keyframe (pre-pass со save/restore состояния,
включая v2 `styles`), между ними offset’ы интерполируются. Углы дополнительно
трекаются per-frame аналитически, если `dynamic_angles=true`.

### Экспорт

| Метод | Описание |
|-------|----------|
| `exportSVG(filepath)` | Экспортировать сцену в SVG через Cairo |
| `exportStylePromptSummary(filepath=None, **kwargs)` | Экспортировать компактный JSON-summary конструкции для AI-генерации style JSON. Если `filepath` не указан, возвращает dict без записи файла. Формат: `animageo-construction-summary/v1`; см. [docs/construction_summary.md](construction_summary.md) |

Пример:

```python
scene.loadGGB(
    'scene.ggb',
    style='base.json',
    export={'size': {'width': 800, 'height': 600}},
)
summary = scene.exportStylePromptSummary('scene.summary.json')
```

Полезные параметры: `include_geometry`, `include_ggb_style`,
`include_style`, `include_resolved_style`, `include_axes`, `max_elements`,
`style_keys`, `source`, `viewport`.

### Вспомогательные

| Метод | Описание |
|-------|----------|
| `addGrid(x_range, y_range)` | Добавить ручную координатную сетку |
| `addCoordinateBackground()` | Добавить фоновую сетку/оси из GGB `<euclidianView>` |
| `waitCut(msg)` | Пауза для видеомонтажа с визуальной меткой |

---

## StyleConfig + resolver

`scene.style_config` (`animageo.style.config.StyleConfig`) — трёхслойная конфигурация:

```python
scene.style_config.presets      # dict — semantic constants (colors/sizes/structures)
scene.style_config.defaults      # DefaultsProfile: per-type baseline в пикселях
scene.style_config.overlay       # StyleOverlay: per_type/per_name + автоматика
scene.style_config.rendering     # dict — low-level render-flags
scene.style_config.reference     # dict — authoring reference canvas
```

Загружается автоматически в `__init__` (builtin.json) и перезагружается в
`applyStyle(style=...)` с deep-merge пользовательского JSON/dict сверху.

```python
from animageo.style.config import StyleConfig
cfg = StyleConfig.load('my_style.json')   # или StyleConfig.load() для builtin-only
cfg.defaults.get('point', 'size_px')       # → 6
```

**Чтение значения стиля.** Вместо `elem.style.get(k, scene.style.X)` используйте единый resolver:

```python
from animageo.style.resolver import resolve, resolved_style, trace

resolve(scene, elem, 'size_px', default=6)   # → значение по цепочке приоритетов
resolved_style(scene, elem)                  # → dict всех ключей (для дебага/снепшотов)
trace(scene, elem, 'size_px')                # → ('elem.style', 99) / ('ggb_style', 10) / …
```

Цепочка приоритетов: `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults.by_type → intrinsic geometry style → default=`. Если `import.enabled=false`, слой `elem.ggb_style` пропускается. Ссылки вида `"color.main"` / `"line_width.bold"` разрешаются автоматически.

`StyleOverlay.apply(scene)` / `scene.applyOverlay()` оставлены как совместимый hook. Overlay-правила не материализуются в `elem.style`; renderer читает их через resolver.

---

## ImportPolicy

Dataclass из `animageo.style.import_policy`. Контролирует как значения из `.ggb` превращаются в `elem.ggb_style` при `loadGGB`. Поля принимают: `None` (fallback на base-режим), литерал, callable `fn(raw, defaults, elem)`, либо DSL-строку (`"const:"`, `"scale:"`, `"quantize:"`, `"remap:"`).

> **Специализация:** `ImportPolicy` сейчас рекомендуется для **raw-GGB трансформаций** (`scale:/quantize:/remap:`). Для стилизации применяемой одинаково к GGB и DSL — используйте `overlay.per_type` / `overlay.per_name` в JSON. См. [docs/import_policies.md](import_policies.md) и [docs/styles.md](styles.md).

```python
from animageo.style.import_policy import ImportPolicy

ImportPolicy.faithful()                       # дефолт: как в GGB (backward compat)
ImportPolicy.style_only()                     # всё из style.json, GGB игнорируется
ImportPolicy.from_dict(cfg)                   # из JSON-словаря (напр. import.policy)
ImportPolicy(size_px=3, font_size_px=14)   # явные overrides
ImportPolicy(stroke_width_px='quantize:[1,2,4]')   # DSL-строка (работает и в Python API)
```

**Поля:** `base`, `size_px`, `stroke_width_px`, `arc_size_px`, `label_offset_px`, `label_color`, `label_visible`, `visible`, `label_text`, `label_mode`, `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator`, `angle_range`, `tick_count`, `font_size_px`, `stroke`, `fill`, `fill_opacity`, `point_shape`, `stroke_opacity`, `stroke_dash_ratio`, `stroke_linecap`. `font_size` остаётся совместимым alias и нормализуется в `font_size_px`.

Правила по типу/имени (`per_type`, `per_name`) задавайте в `overlay`, а не в `ImportPolicy`.

**Методы:**

| Метод | Возвращает | Описание |
|-------|------------|----------|
| `resolve(elem, defaults, ptUnit)` | `dict` | Полный import-style dict (faithful baseline + overrides). Используется для диагностики/совместимости |
| `resolve_overrides_only(elem, defaults, ptUnit)` | `dict` | Только те ключи, которые политика активно переопределяет; `applyStyle` кладёт их в `elem.ggb_style` |

Подробный cookbook для 12 сценариев — [docs/import_policies.md](import_policies.md).
Готовые JSON-пресеты — `examples/policies/*.json`.

---

## Construction

Управление состоянием геометрической конструкции.

| Метод | Описание |
|-------|----------|
| `add(obj)` | Добавить Element, Var или Command |
| `update(name, data)` | Обновить данные элемента |
| `element(name)` | Найти элемент по имени |
| `var(name)` | Найти переменную по имени |
| `objectByName(name)` | Найти Element или Var по имени |
| `rebuild(debug, full)` | Перестроить конструкцию. `full=True` --- все команды |
| `commandByElementName(name)` | Найти команду, создающую элемент |
| `rename(old_name, new_name)` | Переименовать элемент + обновить все ссылки в commands + state |
| `add_and_build(cmd)` | Добавить команду и сразу перестроить только её узел (eager-mode для DSL) |
| `update_tparam(name, tparam)` | Обновить curve/locus-параметр constrained-точки (угол на окружности, линейный t на сегменте/прямой/луче) |
| `get_independents()` | Вернуть dict независимых (анимируемых) элементов для keyframe UI |

---

## Геометрические элементы

Элементы дополнительно хранят `elem.ggb_raw` — словарь сырых GGB-значений (`point_size`, `line_thickness`, `line_opacity`, `line_type`, `arc_size`, `label_offset_px`, `obj_color` и т.д.). `obj_color` содержит исходные `r/g/b/alpha` и алиасы `hex` / `opacity`. Заполняется парсером и используется `ImportPolicy` и `reloadPolicy`.

Полный список имён полей — см. [docs/field_names.md](field_names.md).

### Point
```python
p = Point([x, y])
p.coords     # numpy array [x, y]
p.x, p.y     # float — x- и y-координаты
p.style      # StyleProxy{'label_visible': False, 'label_offset_px': [0.5, 0], 'z_index': 50}
```

### Line
```python
l = Line(normal, offset)     # normal·x = offset
l.normal     # единичный вектор нормали
l.direction  # перпендикуляр к normal
l.offset     # знаковое расстояние до начала координат
l.contains(point_array)      # проверка принадлежности
```

### Segment (наследует Line)
```python
s = Segment(p1_array, p2_array)
s.endpoints  # [[x1,y1], [x2,y2]]
s.start      # np.array[0] — первая точка
s.end        # np.array[1] — вторая точка
s.length     # float
```

### Ray (наследует Line)
```python
r = Ray(start_point, direction_vec)
r.start      # np.array — точка-начало луча
r.direction  # np.array — направление (через Line)
```

### Circle
```python
c = Circle(center, radius)
c.center         # np.array — центр
c.radius         # float
c.radius_squared # computed @property: radius²
c.contains(point_array)
```

### Arc, CircleSector (наследуют Circle)
```python
a = Arc(center, radius, [angle_start, angle_end])
a.angles        # [start, end] в радианах
a.angle_start   # @property на angles[0]
a.angle_end     # @property на angles[1]
```

### Angle
```python
a = Angle(vertex_point, v1_vec, v2_vec)
a.vertex        # np.array — вершина
a.size          # float — величина в радианах
a.value         # @property синоним для .size
a.side1, a.side2 # векторы сторон
a.arc_radius    # радиус рисуемой дуги
a.start_angle   # угол от OX до side1 (радианы)
a.end_angle     # угол от OX до side2
```

### Polygon
```python
p = Polygon([[x1, y1], [x2, y2], ...])
p.vertices      # np.ndarray — массив вершин
```

### Vector
```python
v = Vector([[x1, y1], [x2, y2]])
v.endpoints     # пара точек [start, end]
v.start, v.end  # @property на endpoints[0/1]
v.direction     # end − start
```

### Measure, AngleSize, Boolean (lib_vars)
```python
m = Measure(value, dimension=0)  # dimension: 0=скаляр, 1=длина, 2=площадь
m.value, m.dimension

a = AngleSize(value)             # value в радианах
b = Boolean(True)
b.value                          # True / False
```

### Conic

Коника как 3×3 симметричная матрица. Покрывает окружность, эллипс,
параболу, гиперболу и вырожденные случаи (пары прямых, точка, пустое).

```python
from animageo.geo.lib_elements import Conic
from animageo.geo.lib_conic import ConicType

# Четыре конструктора:
c = Conic(matrix_3x3)                         # сырая матрица
c = Conic.from_ggb_matrix(A0, A1, A2, A3, A4, A5)  # формат GGB <matrix>
c = Conic.from_coeffs(a=1, c=1, f=-1)         # A·x² + B·x·y + C·y² + D·x + E·y + F
c = Conic.from_string("x^2 + y^2 = 4")        # парсинг уравнения (sympy)

# Поля:
c.matrix             # np.ndarray (3×3) — симметричная матрица
c.type               # ConicType.CIRCLE / ELLIPSE / PARABOLA / HYPERBOLA /
                     # INTERSECTING_LINES / PARALLEL_LINES / DOUBLE_LINE /
                     # POINT / EMPTY  (ленивая, кешируется)
c.kind               # @property синоним для .type

# Канонические параметры (None если не соответствует типу):
c.as_circle()        # (center: ndarray, radius: float)
c.as_ellipse()       # {'center', 'semi_axes': (a, b), 'rotation'}
c.as_parabola()      # {'vertex', 'axis', 'perp', 'focal_parameter'}
c.as_hyperbola()     # {'center', 'semi_axes': (a, b), 'rotation'}
c.as_lines()         # List[Line] для вырожденных (0, 1 или 2 линии)
c.as_point()         # Point для POINT

# Стандартный интерфейс элемента:
c.evaluate(x, y)     # pᵀ·matrix·p — значение квадратичной формы в точке
c.contains(pt)       # True если pt принадлежит конике
c.translate(vec), c.scale(ratio)
c.equivalent(other)  # матрицы пропорциональны
```

### Function

Явная функция `y = f(x)` на основе sympy. Парсинг поддерживает GGB-форматы:

```python
from animageo.geo.lib_elements import Function

f = Function.from_string('y = x^2 + 1')
f = Function.from_string('f(x) = sin(x) + cos(2*x)')
f = Function.from_string('i: y = -abs(x) + 4')        # GGB-префикс "label:"
f = Function.from_string('m(x) = If[-1 ≤ x ≤ 1, x^2]') # piecewise

# Поля:
f.expr                     # sympy-выражение RHS
f.var                      # sympy Symbol (обычно x)
f.source                   # исходная строка (для debug/repr)
# @property: .expression, .variable, .callable — алиасы

f(2)                       # численно, через numpy lambdify (без sympy в горячем пути)
f.natural_singularities    # [0.0] для 1/x, [] для полиномов — используется рендером
                           # для разбиения x-диапазона в точках разрыва
f.sample((-2, 2), n=100)   # (n, 2) массив точек
f.translate([dx, dy])      # сдвиг графика
f.contains([x, y])         # True если y == f(x)
```

Поддерживаемые формы выражения:
- полиномиальные: `x^2 + 1`, `(x-3)^3`
- тригонометрия: `sin(x)`, `cos(x)`, `tan(x)`
- `abs`, `sqrt`, `log`, `exp`, `ln`
- `If[cond, then]` / `If[cond, then, else]` (рекурсивно, с поддержкой
  Unicode `≤`, `≥`, `≠` и цепочек `-1 ≤ x ≤ 1`)

### ImplicitCurve

Произвольная неявная кривая `F(x, y) = 0`, когда явное `y = f(x)` или
квадратичная форма не подходят.

```python
from animageo.geo.lib_elements import ImplicitCurve

curve = ImplicitCurve.from_string("(x^2 + y^2)^2 = 8 * (x^2 - y^2)")  # лемниската
curve = ImplicitCurve.from_string("sin(x) + cos(y) = 0.5")
curve = ImplicitCurve.from_string("sqrt(-4*y) + sqrt(abs(x - 1)) = 5")

# Поля:
curve.expr                 # sympy-выражение F(x, y)
curve.var_x, curve.var_y   # sympy Symbol для x и y
curve.source               # исходная строка

curve(x, y)                # скалярное или векторное вычисление
curve.contains([x, y])
curve.translate([dx, dy]), curve.scale(ratio)
```

Рендер через marching squares в `curve_sampling.py` (сетка 128×128 над
viewport), O(grid_n²) работы.

---

## Python DSL

Полный гайд: [docs/python_dsl.md](python_dsl.md). Ниже — краткая сводка.

Exec-based движок. Любой валидный Python-код — поддерживаются циклы, условия, функции, comprehensions, kwargs, tuple-unpack. Полный список ~74 фабрик авто-обнаруживается из `lib_commands.py`.

```python
# Точки и базовые построения
A = Point(0, 0)
B = Point(4, 0)
M = Midpoint(A, B)
s = Segment(A, B)

# Tuple-unpack для команд с несколькими выходами
p, s1, s2, s3 = Polygon(A, B, C)
X, Y = Intersect(line1, circle1)

# Арифметика — регистрирует Add/Sub/Mult/Div-команды
D = A + B
v = B - A
E = 2 * A
neg = -A
m = abs(x)

# Циклы, условия, функции
for i in range(3):
    p = Point(i, 0)        # создаст p, p_2, p_3

def triangle(prefix, side):
    A = Point(0, 0, name=f'{prefix}_A')   # явное имя через kwarg
    B = Point(side, 0, name=f'{prefix}_B')
    return A, B

# Доступ к полям (через прокси)
x_val = A.x                # float
ctr = circ.center          # np.array
seg_len = s.length         # float

# Стили атрибутом
A.style.stroke = '#ff0000'
A.style.size_px = 10
```

### Кривые высокого порядка

```python
# Строковые конструкторы:
f = Function("y = x^2 + 1")
g = Conic("x^2 + y^2 = 4")
h = ImplicitCurve("sin(x) + cos(y) = 0.5")

# DSL-сахар: натуральная запись функции (препроцессор перед AST):
#   name(var) = expr   →   name = Function("y = expr")
f(x) = x^2 + 1
g(t) = 2*t + 1            # → g = Function("y = 2*x + 1")

# Геометрические конструкторы коник:
ell = Ellipse(F1, F2, 5)
par = Parabola(F, directrix_line)
conic5 = Conic(P1, P2, P3, P4, P5)
```

### Команды коник (GGB)

Диспатчеруются на шорткат `K`, работают для всех подходящих `ConicType`:

```python
O          = Center(conic)                  # центр эллипса/гиперболы, вершина параболы
F1, F2     = Focus(ellipse)                 # 2 точки для ellipse/hyperbola
F          = Focus(parabola)                # 1 точка
vs         = Vertex(conic)                  # 4 для эллипса, 2 для гиперболы, 1 для параболы
ax1, ax2   = Axes(ellipse_or_hyperbola)     # большая и малая оси (Line)
d          = Directrix(parabola)
d1, d2     = Directrix(ellipse_or_hyperbola)
e          = Eccentricity(conic)            # Measure(value, dimension=0)
c_lin      = LinearEccentricity(conic)      # Measure(value, dimension=1)
coeffs     = Coefficients(conic)            # [A, B, C, D, E, F]
P          = Point(conic)                   # точка на conic; GGB-импорт сохраняет параметр из XML-координат

polar_line = Polar(point, conic)            # pᵀ·matrix
tangent    = Tangent(point_on_conic, conic) # одна касательная
t1, t2     = Tangent(external_point, conic) # две касательных через pole-polar duality
```

### Пересечения

Все пары первоклассных элементов (Line/Segment/Ray/Circle/Arc/Conic/Function/
ImplicitCurve) поддерживаются. Команда `Intersect` возвращает `Point` или
список `Point`'ов (можно брать индексом):

```python
# Аналитически (Conic):
X, Y    = Intersect(line, conic)       # intersect_Kl: квадратика
A,B,C,D = Intersect(conic1, conic2)    # intersect_KK: pencil + cubic

# Численно (Function/ImplicitCurve):
X       = Intersect(function, line)    # intersect_Fl: sympy.solve → brentq fallback
J, K    = Intersect(function, conic)   # intersect_FK: 1D через подстановку
G, H    = Intersect(implicit, circle)  # intersect_IK: marching squares + Newton
M, N    = Intersect(implicit, line)    # intersect_Il

# Индексный выбор (как в GGB):
A = Intersect(conic, line, index=1)   # первая точка пересечения
B = Intersect(conic, line, 2)         # вторая
```

Индекс всегда 1-based: `1, 2, ...`. Для multi-output порядок тот же:
`P, Q = Intersect(a, b)` соответствует `P = Intersect(a, b, index=1)`
и `Q = Intersect(a, b, index=2)`. Порядок пересечений стабилен и является
частью контракта для DSL, `.ggb` import и export/JSXGraph. Для окружностей
AnimaGeo применяет GeoGebra-like эвристику: точки, уже участвующие во
входных объектах окружности/второго объекта, приоритетно сопоставляются с
вычисленными пересечениями; остальные точки идут во внутреннем
детерминированном порядке.

Hard cap на численные методы гарантирует отсутствие зависаний: 1D
сканы используют `n_samples=401` точек по диапазону `[-50, 50]`; 2D
marching squares — `grid_n=128` × 128 клеток.
