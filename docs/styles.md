# Система стилей AnimaGeo — полный справочник

> Подробный гайд по всем возможностям оформления в AnimaGeo: JSON-схема, per-element ключи, z-index, подписи, автораскладка, ImportPolicy, шрифты, единицы, pixel-invariance, отличия статики и анимации. Для интерактивного прохождения см. `docs/guide/05-styles.html` (стили) и `docs/guide/06-labels.html` (подписи).

---

## Где читать про стили

| Документ | Когда читать |
|---|---|
| `docs/styles.md` | Главный справочник по стилям: концепция слоёв, JSON-схема, resolver, единицы, overlay, rendering, import |
| `docs/architecture.md` | Короткая архитектурная карта: как GGB/DSL проходят через `applyStyle`, `StyleConfig`, `ImportPolicy`, `StyleOverlay` и renderer |
| `docs/import_policies.md` | Только слой GGB import/adaptation: raw GGB values → `elem.ggb_style`, DSL-директивы `scale:` / `quantize:` / `remap:` |
| `docs/field_names.md` | Таблица соответствий: GGB XML → `elem.ggb_raw` → `elem.ggb_style` / `elem.style` → JSON/style layer → renderer |
| `docs/guide/05-styles.html` | HTML-гайд по стилям с примерами |
| `docs/guide/11-reference.html` | HTML-reference по ключам, API и resolver |

## Концепция слоёв

Стили разделены по ответственности, а не по “месту, где удобнее записать ключ”:

| Слой | Ответственность | Что туда класть | Что туда не класть |
|---|---|---|---|
| `presets` | Семантические токены | Цвета, размеры, толщины, font-size, tick/arrow presets | Правила выбора для конкретных объектов |
| `defaults` | Базовый стиль типа элемента | “Все точки по умолчанию такие”, “все углы имеют такой arc radius” | Именные исключения, GGB-specific remap |
| `import` | Адаптация GeoGebra | Маппинг GGB colors/point sizes/line widths, `ImportPolicy` для raw-derived значений | Проектную стилизацию по типам/именам |
| `overlay` | Переопределения поверх импорта и DSL | `per_type`, `per_name`, auto angle radius, label placement | Разбор raw GGB значений |
| `reference` | Эталонный холст стиля | reference width/height для preview и масштабируемого экспорта | Физический размер итогового файла |
| `rendering` | Тонкие настройки вывода | line cap, background, z/layer behavior, global point display | Стили отдельных объектов и GGB remap |
| `elem.ggb_style` | Нормализованный результат GGB import/adaptation | Адаптированные GGB colors/sizes/line types/labels | Ручные DSL/API-правки |
| `elem.style` | Явная настройка конкретного элемента | Локальная правка из DSL/API | Глобальные правила проекта и raw GGB |

Короткое правило: **`import` отвечает “как прочитать GeoGebra”, `overlay` отвечает “как оформить проект”, `rendering` отвечает “как экспортировать/дорисовать”.**

---

## Содержание

1. [Быстрый обзор пайплайна](#1-быстрый-обзор-пайплайна)
2. [Единицы и pixel-invariance](#2-единицы-и-pixel-invariance)
3. [Холст, камера, экспорт](#3-холст-камера-экспорт)
4. [JSON-схема стиля](#4-json-схема-стиля)
5. [Z-index: слои рендеринга](#5-z-index-слои-рендеринга)
6. [Per-element style: все ключи](#6-per-element-style-все-ключи)
7. [Подписи и TeX](#7-подписи-и-tex)
8. [Автоматическая расстановка подписей](#8-автоматическая-расстановка-подписей)
9. [ImportPolicy: гибкий импорт из GeoGebra](#9-importpolicy-гибкий-импорт-из-geogebra)
10. [Статика vs анимация](#10-статика-vs-анимация)
11. [Keyframe-анимации и интерполяция подписей](#11-keyframe-анимации-и-интерполяция-подписей)
12. [Batch-API: массовое изменение стилей](#12-batch-api-массовое-изменение-стилей)
13. [Готовые пресеты](#13-готовые-пресеты)
14. [Рецепты «как добиться X»](#14-рецепты-как-добиться-x)
15. [Известные особенности и подводные камни](#15-известные-особенности-и-подводные-камни)

---

## 1. Быстрый обзор пайплайна

```
.ggb → ggb_parser → Construction (Elements + ggb_raw + ggb_style)
                              │
                              ▼
             applyStyle(style=style.json, reference=..., content=..., export=...)
                              │
                              ├─ GeoStyle    (scene export context)
                              ├─ StyleConfig (builtin.json + user JSON deep-merged)
                              │   ├─ presets
                              │   ├─ defaults.<type>     ← per-type baseline
                              │   ├─ overlay.per_type    ← равенство GGB+DSL
                              │   ├─ overlay.per_name
                              │   ├─ overlay.angle_radius
                              │   └─ overlay.label_placement
                              └─ ImportPolicy (raw-GGB → elem.ggb_style:
                                               scale:/quantize:/remap:)
                              │
                              ▼  addAllGeometry
                   CreateMObject (Element → manim Mobject)
                      └─ resolver.resolve(scene, elem, key):
                          elem.style → per_name → per_type
                          → ggb_style → defaults
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
                  SVG       MP4      Live-preview
```

Каждый элемент несёт три блока стилевых данных:

| Источник | Когда заполняется | Что определяет |
|---|---|---|
| `elem.ggb_raw` | `ggb_parser` | Сырые GGB-значения (`point_size`, `line_thickness`, `line_opacity`, `line_type`, `arc_size`, `label_offset_px`, `obj_color.hex` / `obj_color.opacity`) |
| `elem.ggb_style` | `ggb_parser` + `applyStyle` import rules + `ImportPolicy` | Нормализованный GGB visual baseline. Resolver использует его только если `import.enabled` не `false`. |
| `elem.style` | DSL/API-код, layout/keyframe helpers | Явные per-element записи. Выигрывает у overlay, GGB import и defaults. |
| `scene.style_config` | `StyleConfig.load(style)` | Конфигурация `presets`, `defaults`, `overlay`, `rendering`, `reference`. Читается через `resolver.resolve()`. |
| `GeoStyle` | `applyStyle` из JSON/dict | Scene-level контейнер для палитры, renderer flags и computed `export`. |

Рендер в `CreateMObject`, SVG/PNG/MP4 export и preview читают визуальные значения через `resolver.resolve()`. Поэтому GGB import, defaults, overlay и прямые DSL-записи проходят через один механизм.

### Цепочка приоритетов resolver

`resolver.resolve(scene, elem, key)` обходит слои сверху вниз и возвращает первый найденный:

```
1. elem.style[key]                  ← явная DSL/API-запись
2. overlay.per_name[name][key]      ← точечный оверрайд
3. overlay.per_type[type][key]      ← по типу элемента
4. elem.ggb_style[key]              ← GGB import/adaptation, если import.enabled != false
5. defaults.by_type[type][key]      ← builtin.json + user defaults (deep-merged)
6. intrinsic geometry style         ← внутренние fallback-ключи классов геометрии
7. default=… (аргумент вызова)      ← final fallback
```

**Инвариант**: overlay (per_type/per_name) выигрывает у GGB import/adaptation. Прямые пользовательские записи в `elem.style` считаются explicit и имеют максимальный приоритет. Overlay не материализуется в `elem.style`; рендерный путь читает его через resolver.

### `builtin.json`

Package-shipped файл `animageo/style/builtin.json` содержит разумные pixel-unit дефолты для каждого типа элемента. Он **всегда** загружается первым, user JSON сливается сверху через глубокое слияние (`deep_merge`). Благодаря этому короткий пользовательский файл типа

```json
{"defaults": {"point": {"size_px": 10}}}
```

достаточен, чтобы переопределить точку, сохранив все остальные дефолты (цвета, толщины, углы, …).

### DSL-элементы получают overlay

`ImportPolicy` работает только с raw-GGB значениями, поэтому DSL-элементы
через него не стилизуются. Общие правила по типу/имени задаются в
`overlay.per_type` / `overlay.per_name`; resolver читает такие правила
лениво и одинаково для GGB и DSL.

---

## 2. Единицы и pixel-invariance

В проекте сосуществуют **три системы единиц**, и важно их не путать.

| Пространство | Где живёт | Примеры |
|---|---|---|
| **GGB px** | `ggb_raw`, `elem.ggb_style['*_px']`, `elem.style['*_px']`, `defaults.<type>.*_px` | значения прямо из `.ggb`, import-layer, пользовательские стили, builtin.json |
| **Canonical style px** | `style/*.json` (`presets`, `defaults.*`, `overlay.*`) | все визуальные размеры в пикселях |
| **Internal / manim** | итоговые mobject-координаты и stroke widths | то, что рисуется |

Конверсии централизованы в `animageo/style/scaling.py`:

```python
# GGB px → elem.ggb_style
ggb_point_size_to_style(x)       = x * 2             # pointSize → size_px
ggb_thickness_to_stroke_width(x) = x / 2             # thickness → stroke_width_px
ggb_arc_size_px(x, right=False)  = x  (or x/√2)      # arcSize → arc_size_px
ggb_label_offset_to_style(x, y)  = [x, -y]           # Y инвертируется (GGB-экран ↓ vs математика ↑)

# render-time (resolved style → manim)
stroke_width_to_manim(sw, ptUnit) = sw * 100 / ptUnit
ggb_font_px_to_manim_fontsize(px, ptUnit) = px * 100 / ptUnit
```

> **Phase 4 unit fix.** В canonical schema размеры в `presets`, `defaults.*` и `overlay.*` хранятся в пикселях, а рендерер делит их на `ptUnit` ровно один раз. Это убрало прежний double-scale, из-за которого дуги углов на DSL-сценах могли схлопываться до субпиксельного размера.

### Контракт pixel-invariance

**Все** видимые размеры — диаметры точек, толщины линий, размер шрифта, радиусы дужек углов, смещения подписей — хранятся в **пиксельных** единицах. Рендерер делит их на `ptUnit_style`, поэтому стиль считается относительно reference-холста и масштабируется вместе с reference-картинкой до физического `export.size`.

`ptUnit_ggb` хранится отдельно: это оригинальный масштаб из `.ggb` (пикселей на GGB-единицу). Подписи масштабируются по нему, чтобы при малом холсте не отрывались от геометрии.

### Removed input keys

Исторические ключи `strich_len`, `strich_rshift`, `strich_width`,
`arrow_height`, `arrow_width`, `label_r_offset`, `line_width`, `ang_width`,
`ang_rdefault`, `ang_rshift`, `ang_right`, `font_size` больше не принимаются
в style JSON. Используйте canonical поля (`tick_length_px`, `tick_shift_px`,
`tick_width_px`, `arrow_length_px`, `label_radial_offset_px`,
`stroke_width_px`, `arc_size_px`, `arc_shift_px`, `right_angle_size_px`,
`font_size_px`).

---

## 3. Холст, камера, экспорт

### Параметры экспорта

```python
scene.style.export = {
    'ptUnit':   ...,   # пикселей на manim-единицу в финальном export
    'ptWidth':  ...,   # px — ширина холста
    'ptHeight': ...,   # px — высота
    'ptXZero':  ...,   # px — позиция origin (0,0) от левого края
    'ptYZero':  ...,   # px — позиция origin от верхнего края
    'ptUnit_style': ..., # reference-масштаб для визуальных *_px
    'referenceWidth': ...,
    'referenceHeight': ...,
    'geometryScale': ..., # content -> reference
    'exportScale':   ..., # reference -> physical export
    'ptUnit_ggb': ..., # оригинал ptUnit из .ggb (для pixel-invariant подписей)
    'fontSize': ...,   # GGB-font-size (px) из XML gui.font
}
```

Современный layout разделяет три ответственности:

```python
scene.loadGGB(
    'x.ggb',
    style='style/default.json',
    reference={'size': {'width': 300, 'height': 220}},  # runtime override
    content={'source': 'source_view', 'fit': 'contain'},
    export={'size': {'width': 1920, 'height': 1080}, 'fit': 'contain'},
)
```

- `reference` — эталонный холст, под который автор подбирал стиль. Обычно хранится в style JSON и переопределяется runtime-аргументом только при необходимости.
- `content` — какую область конструкции положить на reference: `source_view`/`ggb_view` или `rendered_bounds`; здесь же `fit`, `padding`, `anchor`, `offset`, `infinite_policy`.
- `export` — физический итоговый файл; это runtime-настройка, в style JSON не хранится.
- `ptUnit_style` — масштаб reference-холста. Через него рендерятся `stroke_width_px`, `size_px`, `font_size_px`, `arc_size_px`, offsets и прочие визуальные пиксели.
- `ptUnit` — масштаб финального export-холста. Его использует SVG/камера для размещения всей картинки.
- `geometryScale` — во сколько раз content/source rect был уложен в reference.
- `exportScale` / `contentScale` — во сколько раз физический файл увеличивает reference-картинку.
- `content.source='rendered_bounds'` сначала строит видимые mobject-ы в исходном масштабе, измеряет их итоговые bounds вместе с подписями и вписывает уже этот прямоугольник. `content.padding` добавляет отступ в source-пикселях. Для `Line`/`Ray` дефолтная политика `content.infinite_policy='ignore'` исключает их из bounds; `'clip'` измеряет их после обрезки исходной камерой.
- Неравномерный stretch не реализован: renderer по-прежнему использует один общий `ptUnit`.

Стиль может хранить эталон:

```json
{
  "reference": {
    "size": { "width": 300, "height": 220 },
    "source": "source_view"
  }
}
```

`reference.source` принимает `manual`, `source_view` или `ggb_view` и служит
описанием происхождения эталона в style JSON. Runtime-выбор области конструкции
делается через `content.source`.

Полная таблица допустимых значений для runtime-блоков `style`, `reference`,
`content` и `export` приведена в [docs/api.md](api.md).

`px_size` больше не является основной публичной моделью. Используйте
`export={'size': {'width': w, 'height': h}}`; одну сторону можно задавать как
`"auto"`.

---

## 4. JSON-схема стиля

Полная документация — в docstring `animageo/style/schema.py`. Ниже — структура и все реально читаемые ключи.

```json
{
    "name": "string (optional)",
    "version": 0.1,

    "presets": {
        "color": {
            "main": "#000000",
            "bold": "#000000",
            "aux": "#888888",
            "accent": "#f15b5b",
            "background": "#ffffff",
            "strong": "#000000"
        },
        "point_size":  { "main": 2.83, "bold": 4.25, "aux": 2.12 },
        "line_width":  { "main": 1,    "bold": 1.5,  "aux": 0.75 },
        "angle_radius": { "main": 17, "shift": 1.5, "right": 17 },
        "tick":  { "main": { "tick_length_px": 9, "tick_width_px": 1.5, "tick_shift_px": 2 } },
        "arrow": { "main": { "arrow_length_px": 11, "arrow_width_px": 7.5 } },
        "font_size": { "main": 14, "bold": 16, "aux": 12 }
    },

    "defaults": {
        "point": {
            "size_px": "point_size.main",
            "fill": "color.strong"
        },
        "segment": {
            "$include": "tick.main",
            "stroke_width_px": "line_width.main"
        },
        "vector": {
            "$include": ["tick.main", "arrow.main"]
        }
    },

    "overlay": {
        "per_type": {
            "angle": { "arc_size_px": 22 },
            "point": { "size_px": 7 }
        },
        "per_name": {
            "A": { "size_px": 99 }
        },
        "angle_radius":    { /* см. §7 */ },
        "label_placement": { /* см. §8 */ }
    },

    "rendering": {
        "background":             "color.background",
        "line_cap":               "butt",
        "right_angle_joint":      "round",
        "polygon_boundary_layer": "top",
        "points_display":         "auto",
        "label_anchor":           "BL",
        "label_value_precision":  1
    },

    "import": {
        "colors":     { "#1565c0": "color.main", "#d32f2f": "color.accent" },
        "point_size": { "5": "point_size.main" },
        "line_width": { "5": "line_width.main" },
        "policy":     { /* см. §9 */ }
    }
}
```

> **Секция `overlay`** (и её `per_type`/`per_name`) — место для стилизации, применяемой после импорта. Работает одинаково для GGB и DSL элементов. `overlay.angle_radius` и `overlay.label_placement` — единственная публичная локация для автоматизмов.

### `presets` — semantic constants

`presets` — реестр именованных смысловых констант. Имена `main`, `bold`,
`aux` — только соглашение; пользователь может добавить любые имена
(`construction`, `answer`, `hidden_helper`) и ссылаться на них из
`defaults`, `overlay`, `rendering` и import-маппингов через
`"<group>.<name>"`, например `"color.accent"` или `"line_width.bold"`.

### Основные группы presets

| Группа.ключ | Назначение | Единицы |
|---|---|---|
| `color.main` / `bold` / `aux` / `background` / `strong` | именованные цвета | hex |
| `point_size.main` / `bold` / `aux` | диаметры точек (`size_px`) | style px |
| `line_width.main` / `bold` / `aux` | толщины линий | style px |
| `angle_radius.main` / `shift` / `right` | радиусы и сдвиги углов | px |
| `tick.main` | структура `tick_length_px/tick_width_px/tick_shift_px` | px |
| `arrow.main` | структура `arrow_length_px/arrow_width_px` | px |
| `font_size.main` / `bold` / `aux` | размер шрифта | px |

### `defaults` — per-type baseline

`defaults` больше не хранит сценовые `angle/tick/arrow/font` настройки.
Это per-type baseline: `defaults.point`, `defaults.segment`, `defaults.angle`,
и т.д. Обычно значения здесь — ссылки на `presets`.

Структурные presets подключаются через `$include`; локальные ключи в этом же
type-блоке выигрывают у включённых значений. Старые
`defaults.angle/tick/arrow/font` всё ещё принимаются loader'ом и нормализуются
в semantic schema перед merge.

### `rendering` — рендер-опции

| Ключ | Значения | Эффект |
|---|---|---|
| `background` | hex или `color.*` | фон сцены: Manim camera/MP4 и SVG viewport |
| `line_cap` | `"butt"` \| `"round"` \| `"square"` | окончания линий |
| `right_angle_joint` | `"auto"` \| `"bevel"` \| `"miter"` \| `"round"` | соединение сторон прямого угла |
| `polygon_boundary_layer` | `"top"` \| `null` | `"top"`: контур полигона всегда поверх заливки (`z_index=10`) |
| `points_display` | `"auto"` \| `"only_labels"` \| `"only_points"` | `only_labels` скрывает точку, показывает подпись; `only_points` — наоборот |
| `label_anchor` | `"TL"`/`"TC"`/`"TR"`/`"ML"`/`"MC"`/`"MR"`/`"BL"`/`"BC"`/`"BR"` | сценовый default-якорь подписей (если не задан per-element). Полная сетка — §7 |
| `label_value_precision` | int | сценовая default-точность value-подписей |

`overlay.label_placement` и `overlay.angle_radius` читаются напрямую из
`scene.style_config.overlay`; в `rendering` эти автоматизмы не допускаются.

### `import` — маппинг значений GGB

По умолчанию применяется **поверх** распарсенных GGB-значений после базового
парсинга. Если указать `"enabled": false`, геометрия и `elem.ggb_raw`
сохраняются, но resolver пропускает `elem.ggb_style`, берёт baseline из
`StyleConfig.defaults`, а `colors` / `point_size` / `line_width` /
`policy` полностью пропускаются. После этого обычным порядком работают
`overlay.per_type` / `overlay.per_name` и explicit DSL/Python-правки.

**`enabled`**: bool, по умолчанию `true`.

**`colors`**: dict вида `"#hex [opacity]" → "color_name|#hex [opacity]"`. Позволяет переопределить всю палитру конструкции одной строкой в стиле.

```json
"colors": {
    "#1565c0":     "color.main",            // GGB-синий → color.main
    "#1565c0 0.1": "color.light 1",         // тот же, но полупрозрачный → light с alpha=1
    "#d32f2f":     "color.accent",
    "#000000 0.6": "#2581b5"          // можно и hex справа
}
```

Результат применения всегда нормализуется в два поля import-layer: цвет записывается в
`elem.ggb_style["fill"]` / `elem.ggb_style["stroke"]` как `#rrggbb`, а opacity
записывается в `fill_opacity` / `stroke_opacity` только если она явно указана
в правой части mapping. Если target-opacity не задана, текущая opacity
элемента сохраняется.

Например, `"#1565c0 0.1": "color.accent 1"` даёт
`fill = "#f15b5b"` и `fill_opacity = 1.0`; `"#1565c0 0.1": "color.accent"` заменит
только цвет и оставит прежнюю `fill_opacity`.

**`line_width`**: маппинг толщин `"N": "line_width.*"` (например `"5": "line_width.main"` — GGB-толщина 5 → `line_width.main`).

**`point_size`**: то же для размеров точек.

**`policy`**: см. §9.

### GGB Graphics View: сетка и оси

При `loadGGB()` парсер читает настройки `<euclidianView>` из `geogebra.xml`
и сохраняет их в `scene.style.export`. Эти поля не являются style overlay для
геометрических элементов: они описывают фон координатной области.

| GGB XML | `style.export` | Использование |
|---|---|---|
| `<evSettings axes>` | `showAxes` | Включает фоновую отрисовку осей |
| `<evSettings grid>` | `showGrid` | Включает фоновую координатную сетку |
| `<evSettings gridIsBold>` | `gridIsBold` | Делает линии сетки немного плотнее |
| `<evSettings gridType>` | `gridType` | Сохраняется для совместимости; сейчас рендерится декартова сетка |
| `<axesColor r g b>` | `axesColor` | Цвет осей, делений и чисел |
| `<gridColor r g b>` | `gridColor` | Цвет линий сетки |
| `<grid distX distY distTheta>` | `gridDistX`, `gridDistY`, `gridDistTheta` | Шаг сетки по X/Y; `distTheta` сохраняется для будущих polar/isometric режимов |
| `<axis id="0|1" show>` | `axes.x.show`, `axes.y.show` | Видимость отдельной оси |
| `<axis ... showNumbers>` | `axes.x.showNumbers`, `axes.y.showNumbers` | Числовые подписи делений |
| `<axis ... tickDistance>` | `axes.x.tickDistance`, `axes.y.tickDistance` | Шаг делений оси |
| `<axis ... axisCross positiveAxis>` | `axes.*.axisCross`, `axes.*.positiveAxis` | Сохраняется; полноценный crossing/positive-only рендер пока не включен |

`addAllGeometry()` перед геометрией добавляет `_coordinate_background`:
сетка рисуется на `z_index=-20`, оси на `z_index=-10`, деления и числа на
`z_index=-9`. Это отдельный фон, не служебные элементы `xAxis` / `yAxis`
из `Construction`.

---

## 5. Z-index: слои рендеринга

```
┌──────────────────────────────────────────────────────┐
│   Z_POINT  = 50     ← точки (самый верх)             │
│   Z_LABEL  = 50     ← подписи на stroke-уровне       │
│   Z_STROKE =  5     ← сегменты, штрихи, дуги-контур  │
│   Z_LINE   =  4     ← линии, окружности              │
│   Z_ANGLE  =  3     ← дуги углов                     │
│   Z_FILL_LABEL = 0.1 ← подписи на fill-уровне        │
│   Z_FILL   =  0.01  ← заливки полигонов/секторов     │
│   Z_FILL_INNER = 0.001 ← зарезервированный нижний fill│
└──────────────────────────────────────────────────────┘
             (ниже = дальше; выше = ближе к зрителю)
```

### Автоматика

При `z_auto=True` (`addAllGeometry`, `addGeoElement`) `CreateMObject` ставит z-index по типу элемента:

| Тип | Основной слой | Fill | Label |
|---|---|---|---|
| `Point` | `Z_POINT` (50) | — | `Z_LABEL` (50) |
| `Segment` / `Circle` / `Arc` / `Vector` | `Z_STROKE` (5) | — | `Z_LABEL` (50) |
| `Angle` | `Z_ANGLE` (3) | — | `Z_LABEL` (50) |
| `Polygon` | `Z_FILL` (0.01) | — | `Z_FILL_LABEL` (0.1) |
| `CircleSector` | `Z_FILL` (0.01) | `Z_FILL` (0.01) | `Z_FILL_LABEL` (0.1) |

Stroke-overlay у полигона всегда ≥ `max(Z_STROKE, zz+0.1)` — контур поверх заливки. Если `rendering.polygon_boundary_layer = "top"`, сегменты-стороны полигона ставятся на `z_index=10` (поверх всего, кроме точек/подписей).

Для стабильности MP4-анимаций AnimaGeo добавляет к каждому фактическому
Manim `z_index` очень маленький tie-breaker по порядку элемента в конструкции
(`construction_index × 1e-6`). Это не меняет уровни `fill`/`stroke`/`point`,
но делает порядок внутри одного слоя детерминированным даже когда `Polygon`
пересоздается через remove+add во время `updateGeoElements()`.

### Явное переопределение

```python
scene.element('poly').style['z_index'] = 100          # полигон — перекроет точки
scene.element('sector').style['z_index_fill'] = 0.2   # только для CircleSector
```

Если ключ `z_index` задан явно — автоматика не активируется.

---

## 6. Per-element style: все ключи

`elem.style` — обычный Python dict, который можно модифицировать на лету. Ниже — **исчерпывающий список** того, что реально читает рендер.

### Видимость

| Ключ | Тип | Default | Что делает |
|---|---|---|---|
| `elem.visible` (атрибут, не ключ) | bool | `True` | Полностью скрывает mobject |
| `visible` | bool | `True` | GGB-«Show object»; читается через resolver |
| `label_visible` | bool | зависит от элемента | Отрисовать подпись |

### Stroke (SVG-совместимые имена)

| Ключ | Тип | Default |
|---|---|---|
| `stroke` | hex | `style.strong` |
| `stroke_width_px` | float (px) | `defaults.<type>.stroke_width_px` |
| `stroke_opacity` | float 0..1 | `1` |
| `stroke_dash_ratio` | float 0..1 \| None | None (solid) |
| `stroke_linecap` | `"butt"`/`"round"`/`"square"` (`"auto"` также принимается runtime map) | `rendering.line_cap` |
| `right_angle_joint` | `"auto"`/`"bevel"`/`"miter"`/`"round"` | `rendering.right_angle_joint` |

### Fill

| Ключ | Тип | Default |
|---|---|---|
| `fill` | hex | `style.background` (для точек — `style.strong`) |
| `fill_opacity` | float 0..1 | `1` |

### Точки

| Ключ | Тип | Default | Эффект |
|---|---|---|---|
| `size_px` | float (px) | `style.dot_size` | диаметр = `size_px / 2 / ptUnit` |
| `point_shape` | enum-строка | `"circle"` | Форма: `"circle"`, `"square"`, `"diamond"`, `"triangle_up"`, `"triangle_down"`, `"triangle_left"`, `"triangle_right"`, `"cross"`, `"plus"`. См. раскладку GGB-пресетов в `docs/field_names.md` §3.3. |

### Углы

| Ключ | Тип | Default | Эффект |
|---|---|---|---|
| `arc_size_px` | float (px) | `defaults.angle.arc_size_px` | Базовый радиус дуги |
| `arc_shift_px` | float (px) | `defaults.angle.arc_shift_px` | Радиальный сдвиг между концентрическими дугами при `tick_count > 1` |
| `angle_range` | `"minor"` \| `"reflex"` | из GGB | `"minor"` = меньший сектор (≤π), `"reflex"` = рефлекс (>π) |
| `right_angle_marker` | bool | авто: `np.isclose(angle, π/2)` | Принудительно квадратная метка прямого угла |
| `right_angle_size_px` | float (px) | `defaults.angle.right_angle_size_px` | Размер квадратного маркера прямого угла |
| `tick_count` | int | 1 | Кратные дуги (двойная, тройная дужка) |

### Сегменты / векторы

| Ключ | Тип | Default | Эффект |
|---|---|---|---|
| `tick_count` | int | нет (ключ может отсутствовать) | Число штрихов-меток на серединe |
| `tick_style` | `"line"` \| `"wave"` | `"line"` | `"wave"` — волнистая пометка вместо прямых штрихов |
| `tick_radius_px` | float | `tick_shift_px * 0.45` | Радиус скругления углов у `tick_style="wave"` |

### Подписи

| Ключ | Тип | Default | Эффект |
|---|---|---|---|
| `label_text` | TeX-строка | `"$" + elem.name + "$"` | Отображаемый текст |
| `label_mode` | `"label"` \| `"value"` \| `"label_value"` | `"label"` | Что показывать: подпись, вычисленное значение или `подпись = значение` |
| `label_value_precision` | int | `1` | Число знаков после запятой для вычисленного значения |
| `label_value_strip_zeros` | bool | `True` | Убирать хвостовые нули (`5.00` → `5`) |
| `label_angle_unit` | `"degree"` \| `"radian"` | `"degree"` | Единица для значений углов |
| `label_value_separator` | str | `" = "` | Разделитель в режиме `label_value` |
| `label_color` | hex | `style.strong` | Цвет текста |
| `label_anchor` | `"TL"`..`"BR"` | `rendering.label_anchor` \| `BL` | Какая часть bbox подписи садится в точку |
| `label_offset_px` | `[x, y]` (GGB px) | `[0, 0]` | Смещение подписи после позиционирования; делится на `ptUnit_ggb` |
| `font_size_px` | float (px) | `defaults.<type>.font_size_px` | Per-element перекрытие размера шрифта |
| `label_radial_offset_px` | float (px) | `defaults.angle.label_radial_offset_px` (`0`) | Радиальный отступ подписи от геометрии (используется у углов) |
| `label_placement_locked` | bool | `False` | Защита от автораскладки |
| `_auto_placed` | bool | `False` (внутренний) | Ставит авто-layout; отключает GGB-descender-коррекцию в `create_label` |

### Z-index (см. §5)

| Ключ | Тип | Default |
|---|---|---|
| `z_index` | float | по типу |
| `z_index_fill` | float | `Z_FILL` |

---

## 7. Подписи и TeX

### 9-точечный якорь

```
    TL ── TC ── TR
    │          │
    ML   MC   MR
    │          │
    BL ── BC ── BR
```

Якорь задаётся в `elem.style['label_anchor']` или сценово в `rendering.label_anchor`. `MC` = «центр подписи в точке» (удобно для углов и взаимодействия с автораскладкой — см. `canonicalize_anchor`).

GeoGebra по умолчанию использует `BL` (bottom-left = базовая линия для заглавных букв).

### TeX-шаблон RusTex

`animageo/ui.py::RusTex` — `pdflatex` + `T2A`/`babel russian`/`utf8`, кастомная отрисовка дробей, `\angle` и `\triangle` в уменьшенном размере.

### Авто-замена Unicode → TeX

`correctedLabel(label)` прогоняет текст через словарь из 96 замен (`·`→`\cdot`, `α`→`\alpha`, `△`→`\triangle`, …), что позволяет писать формулы обычным Unicode в label.

### GGB descender correction

GGB-offset таргетится на низ поля ввода (включая descender padding). У TeX bbox тайтовый, поэтому подпись провисала бы ниже. `create_label` автоматически поднимает её на `ggb_font_px * 0.25 / ptUnit`, **если** `_auto_placed` не выставлен (у авто-размещённых offset-ы уже корректные).

---

## 8. Автоматическая расстановка подписей

Работает в трёх режимах: **статическая one-shot**, **keyframe-snapshot** (для `play_keyframes`) и **per-frame tracker** (для `addUpdater`).

### Статика — по умолчанию

```python
scene.loadGGB(
    'x.ggb',
    style='style/default.json',
    export={'size': {'width': 800, 'height': 600}},
)
scene.autoPlaceLabels()
scene.exportSVG('out.svg')
```

Жадный решатель раскладывает подписи, минимизируя перекрытия. 8 кандидатов направлений (E/NE/N/NW/W/SW/S/SE); самые «трудные» подписи (мало свободных позиций) ставятся первыми.

### Параметры `overlay.label_placement`

| Ключ | Default | Описание |
|---|---|---|
| `enabled` | `false` | Автоматический вызов `autoPlaceLabels()` в конце `loadGGB` |
| `distance_px` | `6` | Базовое расстояние anchor→центр подписи, px |
| `padding_px` | `2` | Зазор вокруг bbox при оценке перекрытий, px |
| `angle_gap_arc_px` | `3` | Зазор между внешней дугой угла и подписью, px. Независим от зазора со сторонами |
| `angle_gap_sides_px` | `3` | Зазор между сторонами угла и bbox подписи (для узких углов), px |
| `w_anchor` | `1.0` | Вес penalty за отклонение от предпочтительного направления |
| `w_label` | `10.0` | Вес перекрытия label×label |
| `w_geom` | `8.0` | Вес перекрытия label×geometry |
| `dynamic_angles` | `false` | Биссектрисы углов пересчитываются per-frame |
| `keyframe_snapshots` | `false` | Раскладка считается на каждом keyframe; между ними интерполируется |
| `canonicalize_anchor` | `false` | Переписывает все якоря в `MC` с компенсированным offset. Убирает скачки при интерполяции. **Ломает snapshot-тесты** (зафиксировавшие старые якоря) — by default off |
| `interpolation` | `"linear"` | Easing для label offset между snapshot-ами: `linear` или `smooth` |
| `ema_alpha` | `0.2` | Вес свежего решателя в EMA (0..1); меньше → плавнее, но медленнее сходится |
| `anchor_flip_frames` | `6` | Schmitt-trigger: сколько подряд кадров решатель должен предлагать другой якорь |
| `solver_every_n_frames` | `2` | Throttling: решатель дёргается раз в N кадров |

### Углы: аналитика вместо кандидатов

Для Angle подпись всегда располагается на биссектрисе. Расстояние:

```
dist = arc_radius_effective + max(half_w, half_h) + gap_arc
# для узких углов дополнительно:
dist ≥ (√(hw² + hh²) + gap_sides) / sin(half_angle)
```

`arc_radius_effective` учитывает множественные дужки: при `elem.style['tick_count'] = N` внешний радиус равен `arc_size_px + (N - 1) * arc_shift_px`, так что подпись не наезжает на внешнюю дужку, даже если их несколько.

`gap_arc` (`angle_gap_arc_px`) отвечает за зазор между дугой и подписью, а `gap_sides` (`angle_gap_sides_px`) — за зазор между подписью и сторонами угла (включается в clamp для узких углов). Обычно достаточно оставить значения по умолчанию; раздельные настройки нужны, например, когда угол очень острый и подпись нужно «утопить» ближе к дуге, не увеличивая общий отступ.

Якорь всегда `MC`.

### Блокировка подписи вручную

```python
scene.element('A').style['label_placement_locked'] = True
scene.element('A').style['label_offset_px'] = [10, -5]
```

### Динамика и keyframe-snapshot

См. §11.

### Автоподбор радиуса дужки угла: `overlay.angle_radius`

Когда угол узкий (малая мера), дужка при фиксированном `arc_size_px` визуально пропадает между двумя близкими сторонами. Включённый `angle_radius` масштабирует базовый радиус по формуле `base * (pivot / angle) ** exp`, а затем зажимает в `[min_px, max_arm_fraction · min(|v1|,|v2|) · ptUnit]`.

Локация в JSON — `overlay.angle_radius`.

| Ключ | Default | Описание |
|---|---|---|
| `enabled` | `false` | Опт-ин. Выключено по умолчанию, чтобы GGB-импорт оставался byte-for-byte faithful |
| `exp` | `0.25` | Показатель `(pivot / angle)^exp`. `0` = без автоподбора |
| `pivot_rad` | `π/2` | Мера, при которой масштаб = 1.0 (углы шире → меньше, уже → больше) |
| `min_px` | `12` | Нижний порог радиуса в пикселях |
| `max_arm_fraction` | `0.65` | Верхний порог как доля от длины короткой стороны |
| `apply_to_right` | `false` | Применять ли clamps (min/max) к маркеру прямого угла |

Per-element escape: `elem.style['auto_radius'] = False` — фиксирует `arc_size_px` для конкретного угла, даже если глобальный флаг включён.

Подпись автоматически сдвигается за новый радиус: `_collect_labels` и рендер используют одну и ту же функцию `compute_effective_arc_size_px`, так что подпись всегда остаётся за пределами внешней дужки.

```json
"overlay": {
    "angle_radius": {
        "enabled": true,
        "exp": 0.3,
        "min_px": 14,
        "max_arm_fraction": 0.55
    }
}
```

---

## 9. ImportPolicy: гибкий импорт из GeoGebra

`ImportPolicy` контролирует, как значения из `.ggb` превращаются в `elem.ggb_style` при `loadGGB`. Полное cookbook — в `docs/import_policies.md`.

### Где берётся

Приоритет (низший → высший):

1. Defaults: `ImportPolicy.faithful()` — как в GGB.
2. `import.policy` внутри style JSON.
3. `loadGGB(..., import_policy=...)` — явный аргумент.
4. `setElementStyle()` — уже после загрузки.

### Поля

Каждое принимает: `None` (fallback), литерал (число/bool/list/dict/hex), Python-callable `fn(raw, defaults, elem)`, или DSL-строку.

| Поле ImportPolicy | GGB-источник | `elem.ggb_style` key |
|---|---|---|
| `size_px` | `<pointSize val>` | `size_px` |
| `stroke_width_px` | `<lineStyle thickness>` | `stroke_width_px` |
| `arc_size_px` | `<arcSize val>` | `arc_size_px` |
| `label_offset_px` | `<labelOffset x y>` | `label_offset_px` |
| `label_color` | `<objColor>` as `obj_color.hex` | `label_color` |
| `label_visible` | `<show label>` | `label_visible` |
| `visible` | `<show object>` | `visible` |
| `label_text` | `<caption>` | `label_text` |
| `angle_range` | `<angleStyle val>` | `angle_range` |
| `tick_count` | `<decoration type>` | `tick_count` |
| `font_size_px` | `<gui><font size>` | `font_size_px` |
| `stroke` | `<objColor>` as `obj_color.hex` | `stroke` |
| `fill` | `<objColor>` as `obj_color.hex` | `fill` |
| `fill_opacity` | `<objColor alpha>` as `obj_color.opacity` | `fill_opacity` |
| `point_shape` | `<pointStyle val>` | `point_shape` |
| `stroke_opacity` | `<lineStyle opacity>` | `stroke_opacity` |
| `stroke_dash_ratio` | `<lineStyle type>` | `stroke_dash_ratio` |
| `stroke_linecap` | — | `stroke_linecap` |

`elem.ggb_raw['obj_color']` stores `r/g/b`, legacy `alpha`, plus normalized
`hex` and `opacity`, so remaps can work with `#rrggbb` and opacity directly.

### Mini-DSL

| Директива | Эффект |
|---|---|
| `"const:3"` | Фиксированное значение `3` |
| `"scale:1.5"` | Умножить сырой GGB-ввод на `1.5` |
| `"quantize:[1,2,4]"` | Снап к ближайшему элементу списка |
| `"remap:{'#f00':'#c00'}"` | Lookup по словарю; miss → исходное |
| `"match_element"` | Копировать stroke в label (sentinel) |
| `"auto"` | Делегировать downstream-алгоритму (sentinel) |

### Горячая замена без парсинга

```python
scene.reloadPolicy(ImportPolicy(size_px=5))
```

Использует закешированные `elem.ggb_raw`, XML не перечитывается.

---

## 10. Статика vs анимация

| Аспект | Статика (SVG) | Анимация (MP4) |
|---|---|---|
| **Подписи** | Одноразово `autoPlaceLabels()` | `keyframe_snapshots` + интерполяция offset, или per-frame tracker |
| **Углы** | Биссектриса один раз | `dynamic_angles` → аналитический пересчёт каждый кадр |
| **Z-index** | Читается на момент экспорта | Переустановка при `updateGeoElements`; равные слои стабилизируются tie-breaker по construction order |
| **stroke_linecap** | Видим | Видим; `butt` даёт резкий конец, `round` — плавный |
| **Шрифт** | GGB-descender-коррекция | Та же коррекция, но `_auto_placed=True` её отключает |
| **ptUnit** | Фиксирован после `applyStyle` | Фиксирован; изменение камеры не пересчитывает |

### Размер холста и анимация

При рендере MP4 manim использует `config.pixel_width/pixel_height`, а не `style.export.ptWidth`. `applyStyle` согласует камеру с export-размерами через соотношение сторон; если оно **не** совпадает с manim-холстом, активная часть укладывается по меньшей стороне.

Для MP4 потребитель обязан явно согласовать Manim config с физическим размером экспорта: `config.pixel_width/config.pixel_height = export["size"]`. Библиотека не выбирает web-quality preset и не должна угадывать bitrate/fps; эти решения остаются на уровне приложения или сервиса.

---

## 11. Keyframe-анимации и интерполяция подписей

### JSON-формат

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

### Типы independent-элементов

| Type | JSON-формат | Интерполяция |
|---|---|---|
| `free_point` | `[x, y]` | линейная по координатам |
| `tparam_point` (circle) | `{"tparam": rad, "direction": "short"\|"cw"\|"ccw"}` | угловая |
| `tparam_point` (segment/line) | `{"tparam": 0..1}` | линейная |
| `number` / `measure` | `float` | линейная |
| `angle` | `float` (rad) | линейная |
| `boolean` | `true`/`false` | snap на t=0.5 |

### Easing

`linear`, `smooth` (default), `in`, `out`, `in_out`.

### Интеграция с автораскладкой

Включите одновременно:

```json
"overlay": {
    "label_placement": {
        "keyframe_snapshots":  true,
        "dynamic_angles":      true,
        "canonicalize_anchor": true,
        "interpolation":       "smooth"
    }
}
```

- `keyframe_snapshots` — pre-pass считает layout на каждом keyframe (со save/restore состояния), offset-ы между snapshot-ами интерполируются.
- `dynamic_angles` — биссектрисы углов пересчитываются аналитически каждый кадр.
- `canonicalize_anchor` — все static-якоря приводятся к `MC` с компенсацией, убирая дискретные скачки.

Без `keyframe_snapshots` или `autoPlaceLabels(dynamic=True)` флаг `dynamic_angles` **ничего не делает** (намеренно — интеграция явная).

### Трекер через `addUpdater`

```python
scene.loadGGB(
    'x.ggb',
    style='style.json',
    export={'size': {'width': 800, 'height': 600}},
)
x = scene.addVar('x', 0)
scene.autoPlaceLabels(dynamic=True)   # ставит LabelTracker
with scene.animating(x):
    scene.play(x.animate.set_value(1), run_time=3)
scene.clearLabelTracker()
```

EMA-сглаживание (`ema_alpha`) + Schmitt-trigger гистерезис якоря (`anchor_flip_frames`) предотвращают дрожание.

---

## 12. Batch-API: массовое изменение стилей

### `setElementStyle`

```python
scene.setElementStyle(['a', 'b', 'c'],
                      stroke='#ff0000',
                      stroke_width=3,
                      fill_opacity=0.5)
```

Проходится по списку имён и пишет все пары в `elem.style`.

### `setVisible`

```python
scene.setVisible(['A', 'B', 'C'], False)
```

### Context manager `animating`

```python
x = scene.addVar('x', 0)
with scene.animating(x):
    scene.play(x.animate.set_value(1), run_time=3)
```

Эквивалентно `addUpdater` → `try/play/clearUpdater`.

### Анимационные хелперы

| Метод | Описание |
|---|---|
| `Show(names, mode='Fade'\|'Create')` / `playShow` | Показать элементы |
| `Hide(names)` / `playHide` | Скрыть |
| `Shade(names)` / `playShade` | Затенить (меняет stroke/fill на `col_shade`) |
| `Restore(names)` / `playRestore` | Восстановить из Shade |
| `Update(names)` / `playUpdate` | FadeOut → пересоздать → FadeIn |
| `UpdateAll()` | То же для всей сцены |
| `ShowCreate(name)` | Create для линий, Fade для заливок и углов |

---

## 13. Готовые пресеты

```
style/
  default.json       Сине-красная палитра (базовая)
  book_blue.json     Для печати, синий
  book_blue2.json    Синий, вариант 2
  book_blue6.json    Синий, вариант 6
  book_blue15.json   Синий, вариант 15
  book_red.json      Для печати, красный
  book_purple.json   Для печати, фиолетовый
  book_green.json    Для печати, зелёный
  pandora.json       «Pandora»-палитра
  style_auto.json    С включённой автораскладкой подписей
  t5.json            Тестовый пресет
```

---

## 14. Рецепты «как добиться X»

### Унификация всех подписей в один цвет и размер

```python
ImportPolicy(font_size_px=14, label_color='#222222')
```

### Точки одного размера

```python
ImportPolicy(size_px=3)
```

### Квантизация толщин

```python
ImportPolicy(stroke_width_px='quantize:[1, 2, 4]')
```

### Брендинг: замена палитры

В JSON:
```json
"import": {
    "colors": {
        "#1565c0": "color.main",
        "#d32f2f":     "color.accent"
    }
}
```

Или через `ImportPolicy`:
```python
ImportPolicy(stroke="remap:{'#1565c0':'#0066cc','#d32f2f':'#c04040'}")
```

### Двойная дуга угла

```python
scene.element('α').style['tick_count'] = 2
scene.element('α').style['arc_shift_px'] = 3  # на 3 px дальше
```

### Полигон «поверх всего»

```json
"rendering": { "polygon_boundary_layer": "top" }
```

Или per-element: `scene.element('poly').style['z_index'] = 100`.

### Скрыть все подписи

```python
ImportPolicy(label_visible=False)
```

### Масштабируемый экспорт в 2×

```python
scene.loadGGB(
    'x.ggb',
    style='style/default.json',
    reference={'size': {'width': 800, 'height': 600}},
    export={'size': {'width': 1600, 'height': 1200}},
)
```

Геометрия и визуальные `*_px` размеры масштабируются в 2× относительно
reference-холста [800, 600].

### Wave-штрихи на равных сторонах

```python
scene.element('a').style['tick_count'] = 2
scene.element('a').style['tick_style'] = 'wave'
scene.element('a').style['tick_radius_px'] = 1.5
```

### Подпись сверху над точкой

```python
scene.element('A').style['label_anchor'] = 'BC'  # bottom-center якорь = подпись выше точки
scene.element('A').style['label_offset_px'] = [0, 10]      # на 10 px выше (положительный Y = вверх в math)
```

### Только подписи, без точек (диаграмма «буквы»)

```json
"rendering": { "points_display": "only_labels" }
```

---

## 15. Известные особенности и подводные камни

Подробно — в `docs/gotchas.md`. Вкратце:

1. **`dynamic_angles=true` сам по себе ничего не делает** — нужен либо `keyframe_snapshots=true`, либо `autoPlaceLabels(dynamic=True)`. Это сознательно, чтобы флаг был дешёв в конфиге.
2. **`canonicalize_anchor=true` ломает snapshot-тесты** — они записали старые якоря. По умолчанию off; включать только для плавной анимации.
3. **TeX bbox-кэш — process-wide**. Ключ `(label_text, font_size)`, так что между сценами в одном процессе переиспользуется корректно. Ручные изменения `RusTex` требуют `clear_bbox_cache()`.
4. **Polygon.become() глючит в manim** → `updateGeoElements` для полигонов работает через remove+add.
   Layer-order при этом не должен плавать: фактические Manim `z_index`
   получают микросдвиг по порядку элемента в конструкции.
5. **Updater на анимируемом ValueTracker получает только start/end** — поэтому `play_keyframes` использует sentinel-Mobject.
6. **`elem.ggb_raw` пусто у элементов из Python-DSL** — `ImportPolicy.resolve_overrides_only()` получит `raw=None`.
7. **`right_angle_marker` auto-detect через `np.isclose(angle, π/2)`** — может ложно сработать на ~89.5°-91°; явно задавайте `right_angle_marker=True/False` если нужна точность.
8. **`arc_size_px` перекрывает `r_offset`** — если оба заданы, `r_offset` игнорируется.
9. **Removed visual fields are rejected.** Старые `line_width`, `font_size`, `strich_*`, `arrow_*`, `label_r_offset`, `ang_*` в style JSON отклоняются; используйте canonical `*_px` ключи.

---

## См. также

- [docs/api.md](api.md) — полный справочник методов `AnimaGeoScene`
- [docs/import_policies.md](import_policies.md) — cookbook с 12 сценариями `ImportPolicy`
- [docs/gotchas.md](gotchas.md) — подводные камни manim/Python/архитектуры
- [docs/architecture.md](architecture.md) — обзор модулей и зависимостей
- [docs/guide/05-styles.html](guide/05-styles.html) — HTML-версия (стили) с интерактивной навигацией, диаграммами и превью; стили объединены в общий guide
- `animageo/style/schema.py` — исчерпывающий docstring JSON-схемы
- `animageo/style/scaling.py` — все формулы конверсии единиц в одном файле
