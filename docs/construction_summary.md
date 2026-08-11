# Compact Construction Summary For AI

Формат `animageo-construction-summary/v1` предназначен для передачи
геометрической конструкции в LLM без сырого `.ggb` XML. Он фиксирует только
то, что обычно нужно для генерации style JSON: имена, типы, компактную
геометрию, видимость, импортированный GGB-стиль, группы элементов и
диагностику парсера.

Основной сценарий:

```python
scene.loadGGB("scene.ggb", style="base.json", export={"size": {"width": 800, "height": 600}})
summary = scene.exportStylePromptSummary("scene.summary.json")
```

Если файл не нужен:

```python
summary = scene.exportStylePromptSummary()
```

Низкоуровневый helper без Manim-сцены:

```python
from animageo.exporters.construction_summary import construction_to_ai_summary

summary = construction_to_ai_summary(construction)
```

## Схема Верхнего Уровня

```json
{
  "schema": "animageo-construction-summary/v1",
  "source": {
    "kind": "ggb",
    "name": "scene.ggb",
    "path": "/abs/path/scene.ggb"
  },
  "viewport": {
    "size": [800, 600],
    "ptUnit": 50,
    "ptUnit_ggb": 50,
    "ptXZero": 400,
    "ptYZero": 300,
    "fontSize": 16
  },
  "stats": {
    "point": 3,
    "segment": 3,
    "angle": 1
  },
  "elements": [],
  "groups": {
    "points": ["A", "B", "C"],
    "segments": ["AB", "BC", "CA"],
    "angles": ["alpha"]
  },
  "warnings": []
}
```

Поля:

| Поле | Назначение |
| --- | --- |
| `schema` | Версия формата. Текущая: `animageo-construction-summary/v1` |
| `source` | Источник конструкции: `ggb`, `dsl_file`, `dsl_inline`, `unknown` |
| `viewport` | Размеры/масштаб экспорта, если известны |
| `stats` | Количество экспортированных элементов по canonical type |
| `elements` | Компактные записи элементов |
| `groups` | Быстрые списки имён по типам |
| `warnings` | `Construction.command_diagnostics`, если parser/rebuild нашли unsupported-команды |
| `vars` | Числовые/булевы/угловые переменные, если есть |
| `truncated` | Метаданные об усечении при `max_elements` |

По умолчанию скрытые служебные `xAxis` и `yAxis` не экспортируются.

## Запись Элемента

```json
{
  "name": "A",
  "type": "point",
  "visible": true,
  "label_visible": true,
  "construction": {
    "command": "Point",
    "inputs": [0, 0],
    "outputs": ["A"]
  },
  "geometry": {
    "coords": [0, 0]
  },
  "ggb_style": {
    "size_px": 10,
    "fill": "#1565c0",
    "stroke": "#000000",
    "label_color": "#1565c0",
    "label_visible": true
  },
  "ggb_raw_summary": {
    "elem_type": "point",
    "point_size": 5,
    "point_style": 0,
    "obj_color": {
      "hex": "#1565c0",
      "opacity": 0
    }
  }
}
```

Общие поля элемента:

| Поле | Назначение |
| --- | --- |
| `name` | Имя элемента в AnimaGeo после нормализации GeoGebra-имени |
| `type` | Canonical type: `point`, `segment`, `line`, `angle`, ... |
| `visible` | Текущая видимость элемента |
| `label_visible` | Видимость подписи, если известна из `ggb_style` или `style` |
| `construction` | Команда, входы и выходы, если элемент создан командой |
| `geometry` | Компактная геометрия, зависящая от типа |
| `ggb_style` | Нормализованный импортированный visual layer |
| `style` | Явные/intrinsic `elem.style`, только если включить `include_style=True` |
| `resolved_style` | Итоговый стиль через resolver, только если включить `include_resolved_style=True` |
| `ggb_raw_summary` | Малый allow-list raw GGB-атрибутов; не сырой XML |

## Geometry Payloads

`point`:

```json
{ "coords": [x, y] }
```

`segment`:

```json
{ "endpoints": [[x1, y1], [x2, y2]], "length": 3.0 }
```

`line`:

```json
{ "normal": [a, b], "direction": [dx, dy], "offset": c }
```

`ray`:

```json
{ "start": [x, y], "direction": [dx, dy] }
```

`vector`:

```json
{ "endpoints": [[x1, y1], [x2, y2]], "direction": [dx, dy] }
```

`angle`:

```json
{
  "vertex": [x, y],
  "side1": [dx1, dy1],
  "side2": [dx2, dy2],
  "size_rad": 1.0472,
  "size_deg": 60.0,
  "start_angle": 0.0,
  "end_angle": 1.0472
}
```

`polygon`:

```json
{ "vertices": [[x1, y1], [x2, y2], [x3, y3]], "vertex_count": 3 }
```

`circle`:

```json
{ "center": [x, y], "radius": 2.0 }
```

`arc` / `circlesector`:

```json
{ "center": [x, y], "radius": 2.0, "angles": [0.0, 1.57] }
```

`conic`:

```json
{ "kind": "ellipse", "matrix": [[...], [...], [...]] }
```

`function`:

```json
{ "source": "y=x^2", "expr": "x**2", "var": "x", "domain": null }
```

`implicitcurve`:

```json
{ "source": "x^2+y^2=1", "expr": "x**2 + y**2 - 1", "var_x": "x", "var_y": "y" }
```

## Параметры Экспортера

`scene.exportStylePromptSummary(filepath=None, **kwargs)` возвращает dict и,
если `filepath` указан, пишет JSON.

Поддерживаемые `kwargs`:

| Параметр | Default | Описание |
| --- | --- | --- |
| `include_geometry` | `True` | Добавлять `geometry` |
| `include_ggb_style` | `True` | Добавлять `ggb_style` |
| `include_style` | `False` | Добавлять explicit/intrinsic `elem.style`; может быть шумно |
| `include_resolved_style` | `False` | Добавлять итоговый стиль через resolver |
| `include_axes` | `False` | Включать служебные `xAxis` / `yAxis` |
| `max_elements` | `None` | Ограничить число элементов; остаток попадёт в `truncated` |
| `style_keys` | встроенный allow-list | Ограничить ключи в style payloads |
| `source` | из сцены | Переопределить `source` |
| `viewport` | из `scene.style.export` | Переопределить `viewport` |

Пример для большого `.ggb`, где LLM нужен только список объектов и импортный
стиль, но не координаты:

```python
summary = scene.exportStylePromptSummary(
    "scene.summary.json",
    include_geometry=False,
    max_elements=300,
)
```

Пример с итоговым стилем после текущего style JSON:

```python
summary = scene.exportStylePromptSummary(
    include_resolved_style=True,
    style_keys=["stroke", "stroke_width_px", "fill", "fill_opacity", "size_px"]
)
```

## Как Использовать В AI-Пайплайне

Для style-generation в запрос к модели обычно передаются:

1. Словесный запрос пользователя.
2. Контекст генерации стилей (`docs/ai_style_generation_context.md` или его
   копия в веб-сервисе).
3. JSON Schema стиля (`docs/ai_style_json_schema.json`).
4. Этот compact summary, если запрос зависит от конкретной конструкции.
5. Инструкция по формату ответа: только JSON или JSON + AnimaGeo Python DSL
   для `scene.loadCode(...)`.

Summary помогает модели:

- не придумывать имена элементов;
- решать, писать ли правило в `overlay.per_type` или `overlay.per_name`;
- видеть, какие GGB visual styles нужно перебить или сохранить;
- предлагать AnimaGeo Python DSL для процедурной достилизации именованных
  объектов через `scene.loadCode(...)`.

Summary не предназначен для полного восстановления конструкции. Это prompt
artifact, а не exchange-формат геометрии. Для AI-создания и редактирования
конструкций summary используется как read-only контекст для
patch-редактирования по именам; см.
[ai_construction_generation_context.md](ai_construction_generation_context.md).
