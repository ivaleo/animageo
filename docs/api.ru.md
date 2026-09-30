# Справочник API

## AnimaGeoScene

Основной класс — наследник `manim.MovingCameraScene`.

### Загрузка данных

| Метод | Описание |
|-------|----------|
| `loadGGB(filepath, style=None, import_policy=None, debug=False, generate_stubs=True, strict=False, reference=None, content=None, export=None)` | Загружает файл .ggb, применяет стиль (при желании через `ImportPolicy`) и отрисовывает геометрию. `style` принимает путь, словарь или `StyleConfig`; `reference` задаёт эталонный холст, для которого создавался стиль; `content` размещает на нём конструкцию; `export` задаёт физический размер вывода. В нестрогом режиме неподдерживаемые команды GGB попадают в `scene.geo.command_diagnostics` без каскада предупреждений; при `strict=True` корневая неподдерживаемая команда превращается в ошибку. При `generate_stubs=True` рядом с .ggb пишется `<basename>_stubs.pyi` |
| `loadCode(filepath, debug=False, show=True)` | Загружает файл Python с кодом DSL (движок exec) |
| `putCode(code, debug=False, show=True)` | Выполняет строку кода Python как DSL (движок exec; см. [docs/python_dsl.md](python_dsl.md)) |
| `applyStyle(style=None, import_policy=None, reference=None, content=None, export=None)` | Применяет стиль к текущей конструкции и пересчитывает раскладку. Внутри: builtin + `style`, затем `reference -> content -> export` |
| `fitView(width=800, height=600, *, padding=40, style=None, passes=2)` | Каноническое кадрирование сцены, построенной в DSL: измеряет фактические границы видимых элементов и вписывает их в холст `width×height` с полем `padding` px. Выполняет `passes` проходов `applyStyle(content='rendered_bounds')` и `updateAllGeometry()` (первый проход устанавливает масштаб для стилей, заданных в пикселях, второй перемеряет уже с правильными размерами точек и подписей). Без `style=` сохраняет текущий `style_config` сцены. Вызывайте, пока нужные элементы видимы (до `HideAll()`); для анимаций оставляйте запас `padding` на движение |
| `reloadPolicy(import_policy)` | Применяет новый `ImportPolicy` без повторного разбора XML (использует закэшированный `elem.ggb_raw`). Затрагивает только элементы GGB |

О политике импорта — в разделе `ImportPolicy` ниже и в [docs/import_policies.md](import_policies.md).

Неподдерживаемые команды GeoGebra диагностируются структурно:

```python
scene.loadGGB('scene.ggb', strict=False)
scene.geo.command_diagnostics
# [{'command': 'Sub', 'signature': ['str', 'AngleSize'],
#   'outputs': ['_3'], 'reason': 'unsupported_signature'}]
```

Команды, получившие `None` только из-за такой корневой неподдерживаемой
команды, добавляются как `dependents` к исходной диагностике и не логируются
скопом как самостоятельные проблемы.

Для выражений диагностика той же формы: `command: 'Expression'`, исходное
выражение в `expression` и объекты конструкции, на которые оно ссылается
(числа, точки, функции), в `parameters`:

| `reason` | Что означает |
|---|---|
| `parametric_dependency_frozen` | Формула ссылается на число (ползунок), но импортирована снимком при значениях на момент загрузки, поэтому объект за числом не следует (например, уравнение коники, не совпавшее с кривой, которую сохранила GeoGebra, — тогда остаётся сохранённая кривая). Также `Point(путь, t)` (`command: 'Point'`), чьё вычисленное положение расходится с сохранённым: остаётся сохранённая точка |
| `expression_parse_error` | Выражение не удалось разобрать; объект строится по сохранённым координатам, если они есть, и не следует за тем, на что ссылается выражение. У функции и неявной кривой сохранённых координат нет — их на сцене не будет |

В остальных случаях формула, ссылающаяся на объекты конструкции, импортируется
как живая зависимость: `f(x) = a x²`, `p: y = a x²`, `g: y = a x + 1` и неявные
кривые пересобираются из формулы с текущими значениями при каждом изменении
числа. То же для координат точек — `x(A)`, `y(A)` (и `x(v)`, `y(v)` вектора) — и
для других функций: `g(t) = y(A) (t - x(B)) + …` следует за `A` и `B`,
`f(t) = g(t) + k (t - x(A))` — за `g`, `k` и `A`. Переменная функции — та, что
названа слева (`g(t) = t²`); `x(` прямо перед скобкой — всегда координата, а не
переменная.

### Параметры раскладки: `style`, `reference`, `content`, `export`

`loadGGB(...)` и `applyStyle(...)` используют один и тот же конвейер:
`style/reference -> content -> export`.

`style` задаёт визуальный стиль:

| Значение | Поведение |
|---|---|
| `None` | встроенный стиль без пользовательского JSON |
| `str` / `PathLike` | путь к JSON-стилю, загружается поверх builtin. Короткое имя пресета (`default`, `book_blue`, `book_green`, `book_purple`, `book_red`) разворачивается в упакованный пресет через `animageo.style.config.resolve_style_input`; существующий файл на диске с тем же именем всегда важнее |
| `dict` | JSON-стиль, переданный напрямую |
| `StyleConfig` | готовая конфигурация; её `source` используется для обратно совместимого `GeoStyle`, а сама конфигурация — для resolver |

`reference` задаёт эталонный холст, для которого считается созданным стиль:

| Поле | Значения | По умолчанию и смысл |
|---|---|---|
| `size` | `[width, height]` или `{"width": w, "height": h}`; каждая сторона — положительное число, `None` или `"auto"` | переопределение `style.reference.size` во время выполнения; если не задано, берётся исходная область просмотра конструкции |
| `source` | `"manual"`, `"source_view"`, `"ggb_view"` | метаданные в JSON-стиле: откуда взялся эталон. Реальная область конструкции выбирается через `content.source` |

`content` описывает, какую область конструкции вписывать в `reference`:

| Поле | Значения | По умолчанию и смысл |
|---|---|---|
| `source` | `"source_view"`, `"ggb_view"`, `"rendered_bounds"`; псевдонимы: `"ggb"` -> `"ggb_view"`, `"bounds"` -> `"rendered_bounds"` | `"source_view"` |
| `fit` | `"contain"`, `"cover"`, `"width"`, `"height"`, `"none"`, `"manual"` | `"contain"` |
| `scale` | положительное число | только для `fit="manual"`; псевдоним `manual_scale` |
| `anchor` | `"top_left"`, `"top"`, `"top_right"`, `"left"`, `"center"`, `"right"`, `"bottom_left"`, `"bottom"`, `"bottom_right"` | `"center"` |
| `offset` | `[x, y]` в пикселях | дополнительный сдвиг после привязки к якорю |
| `padding` | число >= 0 | поле в пикселях источника для `source="rendered_bounds"`; псевдоним `bounds_padding` |
| `infinite_policy` | `"ignore"` или `"clip"` | `"ignore"`: `Line` и `Ray` не расширяют измеряемые границы; `"clip"`: они измеряются после отсечения текущей камерой источника |

`export` описывает физический холст вывода:

| Поле | Значения | По умолчанию и смысл |
|---|---|---|
| `size` | `[width, height]` или `{"width": w, "height": h}`; одна из сторон может быть `None` или `"auto"` | если не задано, размер равен `reference.size`; `[auto, auto]` недопустимо |
| `fit` | `"contain"`, `"cover"`, `"width"`, `"height"`, `"none"`, `"manual"` | `"contain"` |
| `scale` | положительное число | только для `fit="manual"`; псевдоним `manual_scale` |
| `anchor` | те же 9 значений якоря, что и у `content.anchor` | `"center"` |
| `offset` | `[x, y]` в пикселях | сдвиг эталонной картинки внутри холста экспорта |

При загрузке `.ggb` парсер дополнительно переносит параметры
`<euclidianView>` в `style.export`: `showAxes`, `showGrid`, `gridIsBold`,
`gridType`, `axesColor`, `gridColor`, `gridDistX`, `gridDistY`,
`gridDistTheta`, `axes.x` и `axes.y`. `addAllGeometry()` использует их для слоя
`_coordinate_background`: сетка рисуется под геометрией, оси и засечки — над
сеткой, но под всеми объектами конструкции.

### Переменные и обновления

| Метод | Описание |
|-------|----------|
| `addVar(name, value)` | Создаёт анимируемую переменную, возвращает ValueTracker |
| `addUpdater(tracker)` | Привязывает ValueTracker к пересборке геометрии |
| `clearUpdater(tracker)` | Отвязывает ValueTracker |
| `animating(tracker)` | Контекстный менеджер: addUpdater + yield + clearUpdater |
| `updateAllGeometry()` | Пересобирает все объекты manim из текущей геометрии |

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
| `Shade(names)` | `[Animation]` | Приглушить элементы (серый цвет) |
| `Restore(names)` | `[Animation]` | Вернуть из приглушения |
| `Update(names)` | `[Animation]` | Перерисовать элементы |
| `UpdateAll()` | `[Animation]` | Перерисовать все элементы |

Удобные обёртки, которые сами вызывают `self.play(...)`:

```python
self.playShow(['A', 'B', 'C'])
self.playHide(['A'])
self.playShade(['B', 'C'])
self.playRestore(['B', 'C'])
self.playUpdate(['a', 'b'])
```

### Анимация по ключевым кадрам

| Метод | Описание |
|-------|----------|
| `get_independent_elements()` | Возвращает анимируемые входы конструкции для `values`: свободные точки, точки на путях, числа, углы, логические значения и переменные, созданные через `addVar()` |
| `get_element_states()` | Возвращает `{name: {type, visible, style}}` для всех элементов, кроме осей: текущую видимость и разрешённые анимируемые значения стиля; удобно для интерфейса инспектора состояния кадра |
| `play_keyframes(keyframes_data)` | Проигрывает таймлайн из JSON или словаря. `"version": 2` включает стилевые дорожки, видимость и эффекты, кадры камеры и события; v1 без `version` сохранён для совместимости и объявлен устаревшим |
| `apply_keyframes_at(keyframes_data, t)` | Статически применяет состояние таймлайна в момент `t` без `self.play(...)`; удобно для превью одного кадра в SVG или PNG |
| `reveal_construction(lag=0.3, duration=0.5, effect=None, play=True)` | Генерирует таймлайн v2, раскрывающий элементы в порядке зависимостей, и сразу его проигрывает; при `play=False` возвращает словарь таймлайна |

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

Полное описание формата: [docs/keyframes.md](keyframes.md).

### Групповые операции

| Метод | Описание |
|-------|----------|
| `setElementStyle(names, *, update=True, **props)` | Задаёт свойства стиля сразу нескольким элементам |
| `setVisible(names, visible, *, update=True)` | Задаёт видимость сразу нескольким элементам |

```python
self.setElementStyle(['a', 'b', 'c'], stroke='#ff0000', fill_opacity=0.5)
self.setVisible(['A', 'B', 'C', 'D', 'E'], False)
```

### Доступ к данным

| Метод | Возвращает | Описание |
|-------|-----------|----------|
| `element(name)` | `Element` | Элемент конструкции по имени |
| `mobject(name)` | `Mobject` | Объект manim по имени |

### Размещение подписей

| Метод | Описание |
|-------|----------|
| `autoPlaceLabels(dynamic=False)` | Автоматически раскладывает подписи. `dynamic=True` устанавливает `LabelTracker` — последующие анимации через `addUpdater(...)` пересчитывают раскладку на каждом кадре со сглаживанием EMA и гистерезисом якоря |
| `clearLabelTracker()` | Убирает `LabelTracker`. Дальнейшие вызовы `updateVar` не будут запускать покадровый решатель |

Статический вызов (как раньше, однократный):

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
scene.autoPlaceLabels(dynamic=True)   # устанавливает LabelTracker
scene.addUpdater(x)
scene.play(x.animate.set_value(1), run_time=3)
# Углы покадрово следуют за биссектрисой; остальные подписи плавно сходятся
# к решению решателя через EMA. При canonicalize_anchor=True все якоря — 'MC',
# скачков нет.
scene.clearUpdater(x)
scene.clearLabelTracker()
```

Настройки живут в секции `overlay.label_placement` JSON-стиля (см. [docs/styles.md](styles.md)).

Перед началом воспроизведения `play_keyframes()` применяет значения, `visible`
версии 2 и устаревшие `show`/`hide` из первого ключевого кадра, пересобирает
геометрию и обновляет mobject'ы. Поэтому первый отрисованный кадр совпадает с
кадром `0`, даже если сохранённый `.ggb` был в другом состоянии редактора. При
`keyframe_snapshots=true` раскладка вычисляется на каждом ключевом кадре
(предварительный проход с сохранением и восстановлением состояния, включая
`styles` версии 2), а между кадрами смещения интерполируются. Углы
дополнительно отслеживаются аналитически на каждом кадре при
`dynamic_angles=true`.

### Экспорт

| Метод | Описание |
|-------|----------|
| `exportSVG(filepath)` | Экспортирует сцену в SVG через Cairo |
| `exportPDF(filepath, *, dpi=96.0)` | Экспортирует текущий кадр в одностраничный векторный PDF. `dpi` управляет физическим размером страницы; значение по умолчанию (96) воспроизводит экранный размер SVG, а рисунок остаётся векторным и масштабируется в LaTeX через `\includegraphics[width=...]` |
| `exportEPS(filepath, *, dpi=96.0)` | Экспортирует текущий кадр в векторный EPS (Encapsulated PostScript). В EPS нет прозрачности — полупрозрачные заливки растрируются (в журнал пишется предупреждение); чтобы сохранить прозрачность, используйте `exportPDF` |
| `exportTikZ(filepath=None, *, standalone=False, options=None, **kwargs)` | Экспортирует конструкцию в семантический, пригодный для правки TikZ (нативные примитивы `\draw circle`, `ellipse`, `(a)--(b)`, `arc`, настоящие подписи `\node` в LaTeX, `\draw plot coordinates` для выбранных по точкам кривых). Возвращает текст TikZ; при заданном `filepath` дополнительно пишет файл `.tex`. При `standalone=True` картинка оборачивается в компилируемый документ `\documentclass{standalone}`. Передавайте либо экземпляр `options=TikZOptions(...)`, либо именованные параметры (`dpi`, `clip`, `background`, `emit_font_size`, …), но не то и другое сразу. См. [docs/tikz_export.md](tikz_export.md) |
| `exportJSXGraph(filepath=None, *, options=None, **kwargs)` | Экспортирует конструкцию в интерактивную доску JSXGraph. Транслируется граф конструкции, а не отрисованный кадр: свободные точки становятся перетаскиваемыми, точки на кривых — глайдерами, числа — ползунками, а зависимые элементы пересчитываются вживую при перетаскивании. Команды без нативного создателя в JSXGraph превращаются в статическую геометрию и перечисляются в отчёте о покрытии (пишется в журнал на уровне INFO). Возвращает текст HTML/JS/JSON; при заданном `filepath` пишет `.html`, `.js` или `.json`. Передавайте либо `options=JSXGraphOptions(...)`, либо именованные параметры (`output="js"`, `mathjax=False`, `axis=False`, …), но не то и другое сразу |
| `exportStylePromptSummary(filepath=None, **kwargs)` | Экспортирует компактную JSON-сводку конструкции для генерации JSON-стиля с помощью AI. Если `filepath` не указан, возвращает словарь без записи файла. Формат: `animageo-construction-summary/v1`; см. [docs/construction_summary.md](construction_summary.md) |

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

### Утилиты

| Метод | Описание |
|-------|----------|
| `addGrid(x_range, y_range)` | Добавляет координатную сетку вручную |
| `addCoordinateBackground()` | Добавляет фоновую сетку и оси из `<euclidianView>` файла GGB |
| `waitCut(msg)` | Пауза для монтажа видео с визуальным маркером |

---

## StyleConfig и resolver

`scene.style_config` (`animageo.style.config.StyleConfig`) — трёхслойная конфигурация:

```python
scene.style_config.presets       # dict — семантические константы (цвета, размеры, структуры)
scene.style_config.defaults      # DefaultsProfile: базовые значения по типам, в пикселях
scene.style_config.overlay       # StyleOverlay: per_type/per_name плюс автоматика
scene.style_config.rendering     # dict — низкоуровневые флаги рендера
scene.style_config.reference     # dict — эталонный холст, для которого создавался стиль
```

Она загружается автоматически в `__init__` (builtin.json) и перезагружается в
`applyStyle(style=...)`, где пользовательский JSON или словарь накладывается
сверху глубоким слиянием.

```python
from animageo.style.config import StyleConfig
cfg = StyleConfig.load('my_style.json')   # или StyleConfig.load() — только builtin
cfg.defaults.get('point', 'size_px')      # → 6
```

**Чтение значения стиля.** Вместо `elem.style.get(k, scene.style.X)` используйте единый resolver:

```python
from animageo.style.resolver import resolve, resolved_style, trace

resolve(scene, elem, 'size_px', default=6)   # → значение по цепочке приоритетов
resolved_style(scene, elem)                  # → словарь всех ключей (для отладки и снимков)
trace(scene, elem, 'size_px')                # → ('elem.style', 99) / ('ggb_style', 10) / …
```

Цепочка приоритетов: `elem.style → overlay.per_name → overlay.per_type → elem.ggb_style → defaults.by_type → внутренний стиль геометрии → default=`. При `import.enabled=false` слой `elem.ggb_style` пропускается. Ссылки вида `"color.main"` и `"line_width.bold"` разрешаются автоматически.

`StyleOverlay` настраивается через секцию `overlay` JSON-стиля (`per_type` и
`per_name`). Правила overlay никогда не материализуются в `elem.style`;
рендерер читает их лениво через resolver во время `applyStyle` и
`addAllGeometry`.

---

## ImportPolicy

Датакласс из `animageo.style.import_policy`. Управляет тем, как значения из `.ggb` превращаются в `elem.ggb_style` во время `loadGGB`. Поля принимают: `None` (вернуться к базовому режиму), литерал, вызываемый объект `fn(raw, defaults, elem)` или строку DSL (`"const:"`, `"scale:"`, `"quantize:"`, `"remap:"`).

> **Специализация:** сейчас `ImportPolicy` рекомендуется использовать для **преобразований сырых значений GGB** (`scale:`, `quantize:`, `remap:`). Для стилизации, одинаково применяемой к GGB и DSL, используйте `overlay.per_type` и `overlay.per_name` в JSON. См. [docs/import_policies.md](import_policies.md) и [docs/styles.md](styles.md).

```python
from animageo.style.import_policy import ImportPolicy

ImportPolicy.faithful()                       # по умолчанию: как в GGB (обратная совместимость)
ImportPolicy.style_only()                     # всё из style.json, GGB игнорируется
ImportPolicy.from_dict(cfg)                   # из словаря JSON (например, import.policy)
ImportPolicy(size_px=3, font_size_px=14)      # явные переопределения
ImportPolicy(stroke_width_px='quantize:[1,2,4]')   # строка DSL (работает и в Python API)
```

**Поля:** `base`, `size_px`, `stroke_width_px`, `arc_size_px`, `label_offset_px`, `label_color`, `label_visible`, `visible`, `label_text`, `label_mode`, `label_value_precision`, `label_value_strip_zeros`, `label_angle_unit`, `label_value_separator`, `angle_range`, `tick_count`, `font_size_px`, `stroke`, `fill`, `fill_opacity`, `point_shape`, `stroke_opacity`, `stroke_dash_ratio`, `stroke_dash_period_px`, `stroke_linecap`.

Правила по типам и по именам (`per_type`, `per_name`) описывайте в `overlay`, а не в `ImportPolicy`.

**Методы:**

| Метод | Возвращает | Описание |
|-------|------------|----------|
| `resolve(elem, defaults, ptUnit)` | `dict` | Полный словарь импортированного стиля (точная база плюс переопределения). Используется для диагностики и совместимости |
| `resolve_overrides_only(elem, defaults, ptUnit)` | `dict` | Только те ключи, которые политика действительно переопределяет; `applyStyle` кладёт их в `elem.ggb_style` |

Подробный практический сборник рецептов: [docs/import_policies.md](import_policies.md).
Готовые JSON-пресеты: `examples/policies/*.json`.

---

## Construction

Управляет состоянием геометрической конструкции.

| Метод | Описание |
|-------|----------|
| `add(obj)` | Добавить Element, Var или Command |
| `update(name, data)` | Обновить данные элемента |
| `element(name)` | Найти элемент по имени |
| `var(name)` | Найти переменную по имени |
| `objectByName(name)` | Найти Element или Var по имени |
| `rebuild(debug, full)` | Пересобрать конструкцию. `full=True` --- все команды |
| `commandByElementName(name)` | Найти команду, создающую элемент |
| `rename(old_name, new_name)` | Переименовать элемент и обновить все ссылки в командах и состоянии |
| `add_and_build(cmd)` | Добавить команду и сразу пересобрать только её узел (энергичный режим для DSL) |
| `update_tparam(name, tparam)` | Обновить параметр кривой или локуса у связанной точки (угол на окружности, линейный t на отрезке, прямой, луче) |
| `get_independents()` | Вернуть словарь независимых (анимируемых) элементов для интерфейса ключевых кадров |

---

## Геометрические элементы

Элементы дополнительно хранят `elem.ggb_raw` — словарь сырых значений GGB (`point_size`, `line_thickness`, `line_opacity`, `line_type`, `arc_size`, `label_offset_px`, `obj_color` и т. д.). В `obj_color` лежат исходные `r/g/b/alpha` плюс псевдонимы `hex` и `opacity`. Поле заполняет парсер, а читают его `ImportPolicy` и `reloadPolicy`.

Полный список имён полей — в [docs/field_names.md](field_names.md).

### Point
```python
p = Point([x, y])
p.coords     # массив numpy [x, y]
p.x, p.y     # float — координаты x и y
p.style      # StyleProxy{'label_visible': False, 'label_offset_px': [0.5, 0], 'z_index': 50}
```

### Line
```python
l = Line(normal, offset)     # normal·x = offset
l.normal     # единичный вектор нормали
l.direction  # перпендикулярен нормали
l.offset     # расстояние до начала координат со знаком
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
r.start      # np.array — начальная точка луча
r.direction  # np.array — направление (через Line)
```

### Circle
```python
c = Circle(center, radius)
c.center         # np.array — центр
c.radius         # float
c.radius_squared # вычисляемое @property: radius²
c.contains(point_array)
```

### Arc, CircleSector (наследуют Circle)
```python
a = Arc(center, radius, [angle_start, angle_end])
a.angles        # [начало, конец] в радианах
a.angle_start   # @property над angles[0]
a.angle_end     # @property над angles[1]
```

### Angle
```python
a = Angle(vertex_point, v1_vec, v2_vec)
a.vertex        # np.array — вершина
a.size          # float — величина в радианах
a.value         # @property, синоним .size
a.side1, a.side2 # векторы сторон
a.arc_radius    # радиус отрисованной дуги
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
v.endpoints     # пара точек [начало, конец]
v.start, v.end  # @property над endpoints[0/1]
v.direction     # конец − начало
```

### Measure, AngleSize, Boolean (lib_vars)
```python
m = Measure(value, dimension=0)  # dimension: 0=скаляр, 1=длина, 2=площадь
m.value, m.dimension

a = AngleSize(value)             # значение в радианах
b = Boolean(True)
b.value                          # True / False
```

### Conic

Кривая второго порядка как симметричная матрица 3×3. Покрывает окружность,
эллипс, параболу, гиперболу и вырожденные случаи (пары прямых, точка, пустое
множество).

```python
from animageo.geo.lib_elements import Conic
from animageo.geo.lib_conic import ConicType

# Четыре конструктора:
c = Conic(matrix_3x3)                              # сырая матрица
c = Conic.from_ggb_matrix(A0, A1, A2, A3, A4, A5)  # формат <matrix> из GGB
c = Conic.from_coeffs(a=1, c=1, f=-1)              # A·x² + B·x·y + C·y² + D·x + E·y + F
c = Conic.from_string("x^2 + y^2 = 4")             # разбор уравнения (sympy)

# Поля:
c.matrix             # np.ndarray (3×3) — симметричная матрица
c.type               # ConicType.CIRCLE / ELLIPSE / PARABOLA / HYPERBOLA /
                     # INTERSECTING_LINES / PARALLEL_LINES / DOUBLE_LINE /
                     # POINT / EMPTY  (лениво, с кэшированием)
c.kind               # @property, синоним .type

# Канонические параметры (None, если тип не совпадает):
c.as_circle()        # (center: ndarray, radius: float)
c.as_ellipse()       # {'center', 'semi_axes': (a, b), 'rotation'}
c.as_parabola()      # {'vertex', 'axis', 'perp', 'focal_parameter'}
c.as_hyperbola()     # {'center', 'semi_axes': (a, b), 'rotation'}
c.as_lines()         # List[Line] для вырожденных случаев (0, 1 или 2 прямые)
c.as_point()         # Point для POINT

# Стандартный интерфейс элемента:
c.evaluate(x, y)     # pᵀ·matrix·p — значение квадратичной формы в точке
c.contains(pt)       # True, если pt лежит на кривой
c.translate(vec), c.scale(ratio)
c.equivalent(other)  # матрицы пропорциональны
```

### Function

Явная функция `y = f(x)` на основе sympy. Разбор поддерживает формы GGB:

```python
from animageo.geo.lib_elements import Function

f = Function.from_string('y = x^2 + 1')
f = Function.from_string('f(x) = sin(x) + cos(2*x)')
f = Function.from_string('i: y = -abs(x) + 4')        # префикс «метка:» из GGB
f = Function.from_string('m(x) = If[-1 ≤ x ≤ 1, x^2]') # кусочная функция

# Поля:
f.expr                     # выражение sympy для правой части
f.var                      # sympy Symbol (обычно x)
f.source                   # исходная строка (для отладки и repr)
# @property: .expression, .variable, .callable — псевдонимы

f(2)                       # численно, через lambdify для numpy (sympy не на горячем пути)
f.natural_singularities    # [0.0] для 1/x, [] для многочленов — рендерер использует это,
                           # чтобы разбить диапазон x в точках разрыва
f.sample((-2, 2), n=100)   # массив точек (n, 2)
f.translate([dx, dy])      # сдвинуть график
f.contains([x, y])         # True, если y == f(x)
```

Поддерживаемые формы выражений:
- многочлены: `x^2 + 1`, `(x-3)^3`
- тригонометрия: `sin(x)`, `cos(x)`, `tan(x)`
- `abs`, `sqrt`, `log`, `exp`, `ln`
- `If[cond, then]` и `If[cond, then, else]` (рекурсивно, с поддержкой
  юникодных `≤`, `≥`, `≠` и цепочек `-1 ≤ x ≤ 1`)
- неявные произведения: `2x + 1`, `k x`, `(x + 1)(x - 1)`
- имена конструкции, связанные через `parameters=`: числа, координаты `x(A)`,
  `y(A)` точки, заданной как `(x, y)`, другие функции (`g(x)`, заданная
  объектом `Function`) — например
  `Function.from_string('y = x(A) x', parameters={'A': (1, 2)})`

Полный синтаксис формул (допустимые математические функции, `pi`/`e`,
ограничения) — в [docs/python_dsl.md](python_dsl.md#formulas).

### ImplicitCurve

Произвольная неявная кривая `F(x, y) = 0` — для случаев, когда явная
зависимость `y = f(x)` или квадратичная форма не подходят.

```python
from animageo.geo.lib_elements import ImplicitCurve

curve = ImplicitCurve.from_string("(x^2 + y^2)^2 = 8 * (x^2 - y^2)")  # лемниската
curve = ImplicitCurve.from_string("sin(x) + cos(y) = 0.5")
curve = ImplicitCurve.from_string("sqrt(-4*y) + sqrt(abs(x - 1)) = 5")

# Поля:
curve.expr                 # выражение sympy F(x, y)
curve.var_x, curve.var_y   # sympy Symbol для x и y
curve.source               # исходная строка

curve(x, y)                # скалярное или векторизованное вычисление
curve.contains([x, y])
curve.translate([dx, dy]), curve.scale(ratio)
```

Отрисовывается через marching squares в `curve_sampling.py` (сетка 128×128 по
области видимости), объём работы O(grid_n²).

---

## Python DSL

Полное руководство: [docs/python_dsl.md](python_dsl.md). Ниже — краткая выжимка.

Движок на основе exec. Работает любой корректный код Python — циклы, условия, функции, генераторы списков, именованные аргументы, распаковка кортежей. В текущем пространстве имён доступны 100 автоматически найденных фабрик команд поверх 476 сигнатур диспетчеризации из `lib_commands.py`.

```python
# Точки и базовые построения
A = Point(0, 0)
B = Point(4, 0)
M = Midpoint(A, B)
s = Segment(A, B)

# Распаковка кортежа для команд с несколькими выходами
p, s1, s2, s3 = Polygon(A, B, C)
X, Y = Intersect(line1, circle1)

# Арифметика — регистрирует команды Add/Sub/Mult/Div
D = A + B
v = B - A
E = 2 * A
neg = -A
m = abs(x)

# Циклы, условия, функции
for i in range(3):
    p = Point(i, 0)        # создаёт p, p_2, p_3

def triangle(prefix, side):
    A = Point(0, 0, name=f'{prefix}_A')   # явное имя через именованный аргумент
    B = Point(side, 0, name=f'{prefix}_B')
    return A, B

# Доступ к полям (через прокси)
x_val = A.x                # float
ctr = circ.center          # np.array
seg_len = s.length         # float

# Стили как атрибуты
A.style.stroke = '#ff0000'
A.style.size_px = 10
```

### Кривые высших порядков

```python
# Строковые конструкторы:
f = Function("y = x^2 + 1")
g = Conic("x^2 + y^2 = 4")
h = ImplicitCurve("sin(x) + cos(y) = 0.5")

# Синтаксический сахар DSL: естественная запись функции (препроцессор до AST):
#   name(var) = expr   →   name = Function("y = expr")
f(x) = x^2 + 1
g(t) = 2*t + 1            # → g = Function("y = 2*x + 1")
k(x) = 2x (x - x(A))      # `*` можно опускать; x(A) — абсцисса точки A

# Геометрические конструкторы кривых:
ell = Ellipse(F1, F2, 5)
par = Parabola(F, directrix_line)
conic5 = Conic(P1, P2, P3, P4, P5)
```

### Команды для кривых второго порядка (GGB)

Диспетчеризуются по сокращению `K`; работают для любого подходящего `ConicType`:

```python
O          = Center(conic)                  # центр эллипса или гиперболы, вершина параболы
F1, F2     = Focus(ellipse)                 # 2 точки для эллипса и гиперболы
F          = Focus(parabola)                # 1 точка
vs         = Vertex(conic)                  # 4 для эллипса, 2 для гиперболы, 1 для параболы
ax1, ax2   = Axes(ellipse_or_hyperbola)     # большая и малая оси (Line)
d          = Directrix(parabola)
d1, d2     = Directrix(ellipse_or_hyperbola)
e          = Eccentricity(conic)            # Measure(value, dimension=0)
c_lin      = LinearEccentricity(conic)      # Measure(value, dimension=1)
coeffs     = Coefficients(conic)            # [A, B, C, D, E, F]
P          = Point(conic)                   # точка на кривой; импорт GGB сохраняет параметр из координат в XML

polar_line = Polar(point, conic)            # pᵀ·matrix
tangent    = Tangent(point_on_conic, conic) # одна касательная
t1, t2     = Tangent(external_point, conic) # две касательные через двойственность «полюс — поляра»
```

### Пересечения

Поддерживаются все пары полноправных элементов (Line/Segment/Ray/Circle/Arc/
Conic/Function/ImplicitCurve). Команда `Intersect` возвращает `Point` или
список `Point` (с доступом по индексу):

```python
# Аналитические (Conic):
X, Y    = Intersect(line, conic)       # intersect_Kl: квадратное уравнение
A,B,C,D = Intersect(conic1, conic2)    # intersect_KK: пучок плюс кубическое уравнение

# Численные (Function/ImplicitCurve):
X       = Intersect(function, line)    # intersect_Fl: sympy.solve → скан плюс запасное деление пополам
J, K    = Intersect(function, conic)   # intersect_FK: одномерная задача подстановкой
G, H    = Intersect(implicit, circle)  # intersect_IK: marching squares плюс метод Ньютона
M, N    = Intersect(implicit, line)    # intersect_Il

# Выбор по индексу (как в GGB):
A = Intersect(conic, line, index=1)   # первая точка пересечения
B = Intersect(conic, line, 2)         # вторая
```

Индекс всегда считается с единицы: `1, 2, …`. Для команд с несколькими
выходами порядок тот же: `P, Q = Intersect(a, b)` соответствует
`P = Intersect(a, b, index=1)` и `Q = Intersect(a, b, index=2)`. Порядок
пересечений устойчив и является частью контракта для DSL, импорта `.ggb` и
экспорта, в том числе JSXGraph. Для окружностей AnimaGeo применяет эвристику в
духе GeoGebra: точки, уже участвующие во входных объектах окружности или
второго объекта, сопоставляются с вычисленными пересечениями первыми,
остальные идут во внутреннем детерминированном порядке.

Жёсткий предел в численных методах гарантирует отсутствие зависаний:
одномерные сканы используют `n_samples=401` точек на диапазоне `[-50, 50]`,
двумерный marching squares — сетку `grid_n=128` × 128 ячеек.
