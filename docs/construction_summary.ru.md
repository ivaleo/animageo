# Компактная сводка конструкции для AI

Формат `animageo-construction-summary/v1` придуман для того, чтобы передать
геометрическую конструкцию языковой модели, не отдавая ей исходный XML из
`.ggb`. В сводку попадает только то, что обычно нужно для генерации
JSON-стиля: имена, типы, компактная геометрия, видимость, импортированный стиль
GGB, группы элементов и диагностика парсера.

Основной сценарий:

```python
scene.loadGGB("scene.ggb", style="base.json", export={"size": {"width": 800, "height": 600}})
summary = scene.exportStylePromptSummary("scene.summary.json")
```

Если файл не нужен:

```python
summary = scene.exportStylePromptSummary()
```

Низкоуровневый помощник без сцены Manim:

```python
from animageo.exporters.construction_summary import construction_to_ai_summary

summary = construction_to_ai_summary(construction)
```

## Схема верхнего уровня

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
| `schema` | Версия формата. Сейчас: `animageo-construction-summary/v1` |
| `source` | Источник конструкции: `ggb`, `dsl_file`, `dsl_inline`, `unknown` |
| `viewport` | Размер и масштаб экспорта, если известны |
| `stats` | Количество экспортированных элементов по каноническим типам |
| `elements` | Компактные записи элементов |
| `groups` | Быстрые списки имён по типам |
| `warnings` | `Construction.command_diagnostics` — заполняется, если парсер или пересборка встретили неподдерживаемые команды |
| `vars` | Числовые, логические и угловые переменные, если они есть |
| `truncated` | Сведения об обрезке, когда задан `max_elements` |

Скрытые встроенные `xAxis` и `yAxis` по умолчанию не экспортируются.

## Запись элемента

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
| `name` | Имя элемента в AnimaGeo после нормализации имён GeoGebra |
| `type` | Канонический тип: `point`, `segment`, `line`, `angle`, … |
| `visible` | Текущая видимость элемента |
| `label_visible` | Видимость подписи, если она известна из `ggb_style` или `style` |
| `construction` | Команда, входы и выходы — если элемент создан командой |
| `geometry` | Компактная геометрия, зависит от типа |
| `ggb_style` | Нормализованный импортированный визуальный слой |
| `style` | Явный или собственный `elem.style`, только при `include_style=True` |
| `resolved_style` | Итоговый стиль после resolver, только при `include_resolved_style=True` |
| `ggb_raw_summary` | Небольшой белый список сырых атрибутов GGB — но не сам XML |

## Полезная нагрузка geometry

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

## Параметры экспортера

`scene.exportStylePromptSummary(filepath=None, **kwargs)` возвращает словарь и,
если задан `filepath`, записывает JSON.

Поддерживаемые `kwargs`:

| Параметр | По умолчанию | Описание |
| --- | --- | --- |
| `include_geometry` | `True` | Включать блоки `geometry` |
| `include_ggb_style` | `True` | Включать `ggb_style` |
| `include_style` | `False` | Включать явный или собственный `elem.style`; бывает шумным |
| `include_resolved_style` | `False` | Включать итоговый стиль после resolver |
| `include_axes` | `False` | Включать встроенные `xAxis` и `yAxis` |
| `max_elements` | `None` | Ограничить число элементов; остальное уйдёт в `truncated` |
| `style_keys` | встроенный белый список | Ограничить набор ключей в блоках стиля |
| `source` | из сцены | Переопределить `source` |
| `viewport` | из `scene.style.export` | Переопределить `viewport` |

Пример для большого `.ggb`, когда модели нужен только список объектов и
импортированный стиль, но не координаты:

```python
summary = scene.exportStylePromptSummary(
    "scene.summary.json",
    include_geometry=False,
    max_elements=300,
)
```

Пример с итоговым стилем, полученным после применения текущего JSON-стиля:

```python
summary = scene.exportStylePromptSummary(
    include_resolved_style=True,
    style_keys=["stroke", "stroke_width_px", "fill", "fill_opacity", "size_px"]
)
```

## Как использовать сводку в AI-конвейере

Для генерации стиля запрос к модели обычно состоит из:

1. Словесного запроса пользователя.
2. Контекста генерации стилей (`docs/ai_style_generation_context.md`).
3. JSON Schema стиля (`docs/ai_style_json_schema.json`).
4. Этой компактной сводки — если запрос зависит от конкретной конструкции.
5. Указаний по формату ответа: только JSON или JSON плюс код на Python DSL
   AnimaGeo для `scene.loadCode(...)`.

Сводка помогает модели:

- не выдумывать имена элементов;
- решить, куда отнести правило — в `overlay.per_type` или в `overlay.per_name`;
- увидеть, какие визуальные стили GGB нужно перебить, а какие сохранить;
- предложить код на Python DSL AnimaGeo для процедурной доработки стиля
  именованных объектов через `scene.loadCode(...)`.

Сводка не предназначена для полного восстановления конструкции. Это артефакт
для промпта, а не формат обмена геометрией. При создании и редактировании
конструкций с помощью AI сводка служит контекстом только для чтения — правки
вносятся по именам объектов; см.
[ai_construction_generation_context.md](ai_construction_generation_context.md).
