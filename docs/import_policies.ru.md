# ImportPolicy: настраиваемое преобразование стиля при импорте GGB

`ImportPolicy` управляет тем, как визуальные параметры из файла `.ggb`
преобразуются в стили рендера при вызове `AnimaGeoScene.loadGGB()`. По умолчанию
значения GeoGebra сохраняются один к одному для обратной совместимости.
Переопределите политику, чтобы унифицировать шрифты, квантовать толщины,
переназначить цвета или выполнить произвольные преобразования отдельных
элементов.

> **ImportPolicy предназначен только для преобразований данных GGB.**
> Для стилизации, которая одинаково применяется к элементам GGB и DSL — правил
> `per_type` / `per_name` и автоматизации `angle_radius`, `label_placement` —
> используйте раздел `overlay` JSON-стиля. См. [Стили](styles.md) и трёхслойную
> архитектуру StyleConfig.
>
> Коротко: **`ImportPolicy` преобразует исходные значения GGB** через
> `scale:/quantize:/remap:`, а **`overlay` накладывает стиль поверх импорта** и
> работает для любых элементов.

Чтобы целиком отключить визуальный слой импорта GGB, укажите в JSON-стиле:

```json
{ "import": { "enabled": false } }
```

Геометрия `.ggb` всё равно загружается, а `elem.ggb_raw` сохраняется, но
визуальные значения GGB не становятся базой рендера. Resolver переходит к
`StyleConfig.defaults`; разделы `import.colors`, `import.point_size`,
`import.line_width` и `import.policy` пропускаются.

## Быстрый старт

```python
from animageo.animageo import AnimaGeoScene
from animageo.style.import_policy import ImportPolicy

scene = AnimaGeoScene()
scene.loadGGB(
    'file.ggb',
    style='default',
    export={'size': {'width': 800, 'height': 600}},
    import_policy=ImportPolicy(font_size_px=14, label_color='#222222'),
)
```

`style=` принимает короткое имя встроенного пресета (`default`, `book_blue`,
`book_green`, `book_purple`, `book_red`) или путь к собственному JSON-файлу.

## Источники конфигурации

От низшего приоритета к высшему:

1. Встроенные значения `ImportPolicy.faithful()`.
2. Раздел `import.policy` в JSON-стиле.
3. Аргумент `loadGGB(..., import_policy=...)`.
4. Вызов `setElementStyle()` для отдельного элемента после загрузки.

## Поля

Каждое поле принимает `None` — использовать базовый режим, — скалярное
значение, Python-функцию `fn(raw, defaults, elem)` или строковую директиву DSL.
Директивы описаны ниже.

| Поле | Источник GGB | Результат в `elem.ggb_style` |
|---|---|---|
| `size_px` | `<pointSize val>` | `size_px` |
| `stroke_width_px` | `<lineStyle thickness>` | `stroke_width_px` |
| `arc_size_px` | `<arcSize val>` | `arc_size_px` |
| `label_offset_px` | `<labelOffset x y>` | `label_offset_px` |
| `label_color` | `<objColor>` как `obj_color.hex` | `label_color` |
| `label_visible` | `<show label>` | `label_visible` |
| `visible` | `<show object>` | `visible` |
| `label_text` | `<caption>` | `label_text` |
| `label_mode` | `<labelMode val>` (`0/1/2/3/9`) | `label_mode` |
| `label_value_precision` | значение / функция | `label_value_precision` |
| `label_value_strip_zeros` | значение / функция | `label_value_strip_zeros` |
| `label_angle_unit` | значение / функция | `label_angle_unit` |
| `label_value_separator` | значение / функция | `label_value_separator` |
| `angle_range` | `<angleStyle val>` | `angle_range` |
| `tick_count` | `<decoration type>` | `tick_count` |
| `font_size_px` | значение / функция, `raw=None` | `font_size_px` |
| `stroke` | `<objColor>` как `obj_color.hex` | `stroke` |
| `fill` | `<objColor>` как `obj_color.hex` | `fill` |
| `fill_opacity` | `<objColor alpha>` как `obj_color.opacity` | `fill_opacity` |
| `point_shape` | `<pointStyle val>` | `point_shape` |
| `stroke_opacity` | `<lineStyle opacity>` | `stroke_opacity` |
| `stroke_dash_ratio` | `<lineStyle type>` | `stroke_dash_ratio` |
| `stroke_dash_period_px` | — | `stroke_dash_period_px` |
| `stroke_linecap` | — | `stroke_linecap` |

Исходный `obj_color` содержит `r`, `g`, `b`, устаревшее `alpha` и
нормализованные псевдонимы `hex` (`#rrggbb`) и `opacity` для функций политики и
DSL-remap.

`elem.ggb_raw` остаётся диагностическим исходным слоем. `elem.ggb_style` —
нормализованная база импорта GGB, которую resolver читает между `overlay` и
`defaults`. Прямые пользовательские изменения по-прежнему записываются в
`elem.style`.

## Мини-DSL — строковые директивы

| Директива | Значение |
|---|---|
| `"const:3"` | Постоянное значение `3` |
| `"scale:1.5"` | Умножить исходное значение GGB на `1.5` |
| `"quantize:[1,2,4]"` | Округлить до ближайшего элемента списка |
| `"remap:{'#f00':'#c00'}"` | Поиск в словаре; при отсутствии вернуть исходное значение |
| `"match_element"` | Скопировать цвет обводки элемента в подпись — sentinel |
| `"auto"` | Передать решение следующему алгоритму — sentinel |

Обычные строки, например `"#000000"`, проходят без изменений.

Строки DSL ведут себя одинаково при загрузке из JSON через `from_dict` и при
прямой передаче конструктору Python. Например,
`ImportPolicy(stroke_width_px='quantize:[1,2,4]')` эквивалентен такой же записи
в JSON. Разбор выполняется в `__post_init__`. Полноценные lambda-функции
доступны только из Python API.

## Переопределения проекта

`ImportPolicy` больше не содержит `per_type` / `per_name`. Эти правила не
адаптируют исходные значения GeoGebra, а задают стиль проекта, поэтому находятся
в `overlay`. Там они одинаково действуют на импортированные GGB-объекты и
объекты, созданные DSL:

```json
"overlay": {
    "per_type": { "polygon": { "fill_opacity": 0.15 } },
    "per_name": { "A": { "size_px": 99 } }
}
```

## Рецепты

### 1. GeoGebra без изменений — по умолчанию

```python
scene.loadGGB('file.ggb')
```

### 2. Всё из style.json, размеры и цвета GGB игнорируются

```python
scene.loadGGB(
    'file.ggb',
    import_policy=ImportPolicy.style_only(),
    style='default',
)
```

### 3. Единые подписи: 14 pt, тёмно-серые, для всех элементов

```python
ImportPolicy(font_size_px=14, label_color='#222222')
```

### 4. Единый размер точек

```python
ImportPolicy(size_px=3)
```

### 5. Масштабирование размеров

```python
ImportPolicy(
    size_px=lambda raw, d, e: raw * 1.5,
    stroke_width_px=lambda raw, d, e: raw * 1.2,
)
```

Эквивалент в JSON:

```json
{ "size_px": "scale:1.5", "stroke_width_px": "scale:1.2" }
```

### 6. Квантованные толщины

```python
ImportPolicy(stroke_width_px='quantize:[1, 2, 4]')
```

### 7. Замена фирменного цвета

```python
ImportPolicy(stroke="remap:{'#1565c0':'#0066cc'}")
```

### 8. Правила по типу и имени через overlay

```json
{
  "overlay": {
    "per_type": {
      "polygon": { "fill_opacity": 0.1, "stroke": "#888888" }
    },
    "per_name": {
      "A": { "size_px": 18, "label_color": "#ff0000" }
    }
  }
}
```

### 9. Чёрно-белый режим

```python
ImportPolicy(
    stroke='#000000',
    fill='#cccccc',
    label_color='#000000',
)
```

### 10. Скрыть все подписи

```python
ImportPolicy(label_visible=False)
```

### 11. Заменить политику без повторного разбора

```python
scene.loadGGB('file.ggb')
# ... изучение результата ...
scene.reloadPolicy(ImportPolicy(size_px=5))
```

## Формат JSON в файлах стилей

```json
{
  "import": {
    "policy": {
      "preset": "custom",
      "size_px": "scale:1.5",
      "stroke_width_px": "quantize:[1,2,4]",
      "font_size_px": 14,
      "label_color": "#222222",
      "stroke": "remap:{'#1565c0':'#0066cc'}"
    }
  }
}
```

## Особенности поведения

- База `faithful()` по умолчанию начинается с текущего результата парсера и
  внешне не отличается от версий до появления ImportPolicy.
- База `style_only()` полностью игнорирует `ggb_raw` и начинается со словаря
  `defaults`, переданного в `resolve()`. Для полного эффекта следующий уровень
  передаёт значения по умолчанию из `GeoStyle`.
- Функции всегда получают **исходное** значение GGB, например `pointSize=5`, а
  не `size=10`. Если поле политики активно, стандартные коэффициенты
  преобразования не применяются.
- `label_offset` проходит тот же путь, но `y` из GGB не инвертируется внутри
  функции. Если нужны смещения в математических координатах, явно верните
  `[x, -y]`.
