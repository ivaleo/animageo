# Быстрый старт

## Установка

```bash
pip install animageo
```

Основные зависимости (`numpy`, `manim >= 0.20.1`, `pycairo`, `sympy`, `scipy`)
устанавливаются автоматически. Для рендеринга MP4/GIF дополнительно требуется
рабочее окружение Manim: ffmpeg и установленный LaTeX для текстовых подписей.

## Минимальный пример

```python
from animageo import *

class MyScene(AnimaGeoScene):
    def construct(self):
        # Загружаем конструкцию GeoGebra
        self.loadGGB('triangle.ggb',
                     style='default',
                     export={'size': {'width': 800, 'height': 600}})

        # Показываем все элементы
        self.wait(2)

        # Экспортируем в SVG
        self.exportSVG('triangle.svg')
```

Запуск:

```bash
manim my_scene.py MyScene -ql
```

Короткие имена стилей (`default`, `book_blue`, `book_green`, `book_purple`,
`book_red`) ссылаются на пресеты из пакета. Можно передать путь к собственному
JSON-файлу стиля, а если опустить `style`, будут использованы встроенные
значения по умолчанию.

## Добавление собственной геометрии

Конструкции расширяются с помощью Python DSL, который выполняет полноценный
Python-код: циклы, условия, функции, именованные аргументы и списковые
включения. Подробности — в разделе [Python DSL](python_dsl.md).

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.loadGGB('scene.ggb', style='default',
                     export={'size': {'width': 800, 'height': 600}})

        # Добавляем элементы через Python DSL
        self.putCode('''
            M = Midpoint(A, B)
            h = Segment(C, M)

            # Можно использовать обычные конструкции Python
            for i in range(3):
                p = Point(i, 0)          # создаёт p, p_2, p_3

            # Доступ к полям и настройка стиля
            M.style.stroke = '#ff0000'
            x_val = A.x                  # координата как float
        ''')

        # Или загружаем файл .py, лежащий рядом со сценой
        self.loadCode('extra_constructions.py')
```

## Анимация с помощью переменных

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.loadGGB('scene.ggb', style='default',
                     export={'size': {'width': 400, 'height': 400}})

        # Создаём переменную и связываем её с конструкцией
        t = self.addVar('t', 0.0)
        self.addUpdater(t)

        # Анимируем
        self.play(t.animate.set_value(1.0), run_time=3)
        self.clearUpdater(t)
```

## Анимация по ключевым кадрам

Для сохранённых таймлайнов, веб-превью и воспроизводимых рендеров используйте
`play_keyframes()`. Сначала проверьте, какие входные данные можно анимировать:

```python
independents = self.get_independent_elements()
```

Минимальный таймлайн v2:

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

Формат v2 поддерживает треки стилей, видимость с эффектами появления и
исчезновения, 17 функций плавности, `@camera`, события акцентирования,
`reveal_construction()` и статические превью через `apply_keyframes_at()`.
Полное описание находится в разделе [Анимация по ключевым кадрам](keyframes.md).

## Управление видимостью

```python
self.HideAll()                              # Скрыть всё
self.playShow(['A', 'B', 'C'])              # Показать точки
self.playShow(['poly1'], mode='Create')     # Анимация построения
self.playShade(['A', 'B'])                  # Приглушить
self.playRestore(['A', 'B'])                # Восстановить
```

## Коники, функции и неявные кривые

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.applyStyle(style='default',
                        export={'size': {'width': 800, 'height': 600}})

        self.putCode('''
            # Коника из уравнения: тип определяется автоматически.
            g = Conic("x^2 + y^2 = 4")

            # Функция через строковый конструктор.
            f = Function("y = x^2 - 1")

            # Или краткая форма, которую переписывает препроцессор DSL.
            h(x) = -abs(x) + 4

            # Пересечения работают для всех типов.
            A, B = Intersect(f, g)

            # Команды для коник в стиле GGB.
            O = Center(g)
            F1, F2 = Focus(g)

            # Неявная кривая (marching squares).
            lemn = ImplicitCurve("(x^2 + y^2)^2 = 8 * (x^2 - y^2)")
        ''')

        self.exportSVG('conics.svg')
```

## Переопределение стилей

Стилизация в AnimaGeo состоит из трёх слоёв; подробности — в разделе
[Стили](styles.md):

1. **`defaults`** в JSON и поставляемом с пакетом `builtin.json` — базовые
   пиксельные значения по типам. Работают и для DSL-, и для GGB-элементов.
2. **`overlay.per_type` / `per_name`** — накладываются поверх импортированных
   значений и также работают для любых элементов.
3. **`ImportPolicy`** (`loadGGB(..., import_policy=...)`) — специализированные
   преобразования **исходных значений GGB** (`scale:/quantize:/remap:`), которые
   не действуют на DSL-элементы.

Единый стиль для элементов GGB и DSL через `overlay`:

```json
"overlay": {
    "per_type": {
        "point":   {"size_px": 7, "fill": "#000"},
        "segment": {"stroke_width_px": 2.2},
        "angle":   {"arc_size_px": 22, "label_color": "#222"}
    }
}
```

Альтернативный вариант — Python API при загрузке файла GGB:

```python
from animageo.style.import_policy import ImportPolicy

scene.loadGGB(
    'scene.ggb',
    style='default',
    export={'size': {'width': 800, 'height': 600}},
    import_policy=ImportPolicy(
        stroke_width_px='quantize:[1, 2, 4]',  # группы толщин GGB
        label_color='#222222',                 # единый цвет подписей
    ),
)
```

Полная подборка примеров: [Правила импорта GeoGebra](import_policies.md).

## Экспорт

```python
# SVG (через Cairo)
self.exportSVG('output.svg')

# TikZ для LaTeX / интерактивный JSXGraph
self.exportTikZ('output.tex')
self.exportJSXGraph('board.html')

# MP4 — рендерится через Manim
# manim scene.py MyScene -qh
```
