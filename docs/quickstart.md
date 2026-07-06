# Быстрый старт

## Установка

```bash
pip install animageo
```

Зависимости: `numpy`, `manim >= 0.20.1`, `pycairo`, `lark`.

## Минимальный пример

```python
from animageo import *

class MyScene(AnimaGeoScene):
    def construct(self):
        # Загрузить конструкцию из GeoGebra
        self.loadGGB('triangle.ggb',
                     style='style/default.json',
                     export={'size': {'width': 800, 'height': 600}})

        # Показать все элементы
        self.wait(2)

        # Экспортировать в SVG
        self.exportSVG('triangle.svg')
```

Запуск:

```bash
manim my_scene.py MyScene -ql
```

## Добавление своей геометрии

Используется exec-based Python DSL — полный Python (циклы, условия,
функции, kwargs, comprehensions). Подробности — [docs/python_dsl.md](python_dsl.md).

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.loadGGB('scene.ggb', style='style/default.json',
                     export={'size': {'width': 800, 'height': 600}})

        # Добавить элементы через Python DSL
        self.putCode('''
            M = Midpoint(A, B)
            h = Segment(C, M)

            # Python-конструкции тоже работают
            for i in range(3):
                p = Point(i, 0)          # создаст p, p_2, p_3

            # Доступ к полям и стили
            M.style.stroke = '#ff0000'
            x_val = A.x                  # координата как float
        ''')

        # Или загрузить из файла (файл .py рядом со сценой)
        self.loadCode('extra_constructions.py')
```

## Анимация с переменными

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.loadGGB('scene.ggb', style='style/default.json',
                     export={'size': {'width': 400, 'height': 400}})

        # Создать переменную и привязать к конструкции
        t = self.addVar('t', 0.0)
        self.addUpdater(t)

        # Анимировать
        self.play(t.animate.set_value(1.0), run_time=3)
        self.clearUpdater(t)
```

## Keyframe-анимация

Для сохранённых таймлайнов, веб-превью и повторяемого рендера используйте
`play_keyframes()`. Сначала посмотрите, какие входы можно анимировать:

```python
independents = self.get_independent_elements()
```

Минимальный v2-таймлайн:

```python
self.play_keyframes({
    "version": 2,
    "keyframes": [
        {"t": 0, "values": {"A": [0, 0], "x": 35}},
        {"t": 2, "values": {"A": [4, 2], "x": 110},
         "styles": {"a": {"stroke": "#d05456"}},
         "visible": {"helper": False},
         "easing": "smooth"},
    ],
})
```

V2 поддерживает анимацию стилей, видимости с эффектами, 17 easing-имен,
`@camera`, events-акценты, `reveal_construction()` и статический preview через
`apply_keyframes_at()`. Формат подробно описан в [docs/keyframes.md](keyframes.md).

## Управление видимостью

```python
self.HideAll()                              # Скрыть все
self.playShow(['A', 'B', 'C'])              # Показать точки
self.playShow(['poly1'], mode='Create')     # Анимация построения
self.playShade(['A', 'B'])                  # Затенить
self.playRestore(['A', 'B'])                # Восстановить
```

## Коники, функции и неявные кривые

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.applyStyle(style='style/default.json',
                        export={'size': {'width': 800, 'height': 600}})

        self.putCode('''
            # Коника из уравнения (тип определяется автоматически).
            g = Conic("x^2 + y^2 = 4")

            # Функция через строковый конструктор.
            f = Function("y = x^2 - 1")

            # Или в краткой «sugar»-форме (препроцессор DSL перепишет).
            h(x) = -abs(x) + 4

            # Пересечения работают для любых типов.
            A, B = Intersect(f, g)

            # Команды коник в стиле GGB.
            O = Center(g)
            F1, F2 = Focus(g)

            # Неявная кривая (marching squares).
            lemn = ImplicitCurve("(x^2 + y^2)^2 = 8 * (x^2 - y^2)")
        ''')

        self.exportSVG('conics.svg')
```

Полный набор примеров — `examples/conics_functions/`.

## Подмена стилей

Стилизация в AnimaGeo имеет три слоя (см. [docs/styles.md](styles.md)):

1. **`defaults`** в JSON (и package-shipped `builtin.json`) — per-type baseline в пикселях. Работает и в DSL, и в GGB.
2. **`overlay.per_type` / `per_name`** — поверх импорта, тоже работает везде.
3. **`ImportPolicy`** (`loadGGB(..., import_policy=...)`) — специализирован под **raw-GGB трансформации** (`scale:/quantize:/remap:`); для DSL-элементов бесполезен.

Пример унификации стилей через `overlay` (одинаково для GGB и DSL):

```json
"overlay": {
    "per_type": {
        "point":   {"size_px": 7, "fill": "#000"},
        "segment": {"stroke_width_px": 2.2},
        "angle":   {"arc_size_px": 22, "label_color": "#222"}
    }
}
```

Альтернативно — через Python-API при загрузке GGB:

```python
from animageo.style.import_policy import ImportPolicy

scene.loadGGB(
    'scene.ggb',
    style='style/default.json',
    export={'size': {'width': 800, 'height': 600}},
    import_policy=ImportPolicy(
        stroke_width_px='quantize:[1, 2, 4]',  # квантизация толщин GGB
        label_color='#222222',                 # единый цвет подписей
    ),
)
```

Полный cookbook — [docs/import_policies.md](import_policies.md).

## Экспорт

```python
# SVG (через Cairo)
self.exportSVG('output.svg')

# MP4 --- запускается через manim
# manim scene.py MyScene -qh
```
