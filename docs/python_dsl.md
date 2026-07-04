# AnimaGeo Python DSL

Path-B DSL — «нормальная Python-оболочка» для построения геометрических
конструкций. Любой валидный Python-код работает как DSL, а вызовы
фабрик (`Point`, `Midpoint`, `Intersect`, …) одновременно выполняются
и регистрируются в графе зависимостей `Construction`.

> **Статус:** exec-движок по умолчанию, legacy доступен через флаг.
> 857 тестов зелёные.
>
> Точки входа:
> * `scene.putCode(code)` / `scene.loadCode(filepath)` — по умолчанию `engine='exec'`
> * `scene.loadGGB(filepath)` — GGB → exec (через `ggb_parser`, flipped in Phase 3)
> * `dsl.run(constr, code)` — прямой вызов
> * `with dsl.scope(constr): ...` — contextvar binding для file-mode

## Оглавление
- [Быстрый старт](#быстрый-старт)
- [Синтаксис](#синтаксис)
- [Фабрики](#фабрики)
- [Именование элементов](#именование-элементов)
- [Доступ к полям](#доступ-к-полям)
- [Стили](#стили)
- [Что запрещено](#что-запрещено)
- [Отличия от legacy-парсера](#отличия-от-legacy-парсера)

## Быстрый старт

Через отдельный `Construction`:

```python
from animageo.geo.construction import Construction
from animageo.parsers import dsl

c = Construction()
dsl.run(c, """
    A = Point(0, 0)
    B = Point(4, 0)
    C = Point(0, 3)
    p, s1, s2, s3 = Polygon(A, B, C)
    M = Midpoint(A, B)
    style(M, stroke='#ff0000', size=10)
""")
```

Через manim-сцену (`AnimaGeoScene`):

```python
class MyScene(AnimaGeoScene):
    def construct(self):
        self.putCode("""
            A = Point(0, 0)
            B = Point(3, 4)
            M = Midpoint(A, B)
        """, engine='exec')
        self.showAllGeometry()
```

Или импорт фабрик прямо в .py-файле (с IDE-подсказками):

```python
from animageo.parsers.dsl.namespace import Point, Midpoint, style
# Для прямого вызова нужен активный Construction в ContextVar —
# см. dsl.registrar.set_current_construction или используй
# scene.putCode(code, engine='exec').
```

## Синтаксис

Весь Python работает:

```python
# циклы
for i in range(5):
    p = Point(i, 0)            # создаст p, p_2, p_3, p_4, p_5

# условия
for i in range(10):
    if i % 2 == 0:
        p = Point(i, 0)

# функции
def triangle(prefix, side):
    A = Point(0, 0, name=f"{prefix}_A")
    B = Point(side, 0, name=f"{prefix}_B")
    C = Point(side/2, side*0.866, name=f"{prefix}_C")
    return A, B, C

triangle("t1", 3)
triangle("t2", 5)

# list comprehensions тоже работают
radii = [r for r in range(1, 6)]
circles = [Circle(Point(0, 0, name=f"O_{i}"), r) for i, r in enumerate(radii)]

# математика
import_notationless = 1  # `import` запрещён, но ``math``/``pi``/``sqrt``
                         # доступны глобально в DSL-namespace
A = Point(sqrt(2), pi/2)
```

## Фабрики

Любое CamelCase-имя, для которого в `animageo/geo/lib_commands.py`
есть соответствующая диспетчеризуемая функция, автоматически
становится фабрикой. Не нужно ничего регистрировать руками.

Ключевые фабрики:

| Конструкторы | Команды |
|---|---|
| `Point`, `Line`, `Segment`, `Ray`, `Circle`, `Arc`, `CircleSector`, `Angle`, `Polygon`, `Vector`, `Conic`, `Function`, `ImplicitCurve` | `Midpoint`, `Distance`, `Length`, `Radius`, `Center`, `Vertex`, `Focus`, `Intersect`, `AreCollinear`, `Perpendicular`, `Parallel`, `Tangent`, `Polar`, … (~300) |

Неизвестное имя → `NameError` (чисто; не молчаливая ошибка
«no implementation» из legacy).

## Именование элементов

### По переменной слева

```python
A = Point(0, 0)        # элемент зарегистрирован как "A"
```

### В цикле — автоматическая уникализация

```python
for i in range(3):
    p = Point(i, 0)    # элементы: p, p_2, p_3
```

### В функции — тоже уникализация (тело `def` = loop-scope)

```python
def make():
    A = Point(0, 0)
    return A

make()    # элемент: A
make()    # элемент: A_2
```

### Явное имя через `name=`

```python
def triangle(prefix):
    A = Point(0, 0, name=f"{prefix}_A")   # элемент: <prefix>_A
    B = Point(1, 0, name=f"{prefix}_B")
    return A, B
```

Если `name=` указан и имя уже занято — `ValueError` (не молчаливая
коллизия). Python-переменная `A` всё равно биндится к прокси.

### Tuple-unpack для команд с несколькими выходами

```python
a, b = Intersect(c, L)                    # две точки пересечения
p, s1, s2, s3 = Polygon(A, B, C)          # полигон + три стороны
```

Transform инжектит `_outputs=N` в вызов, чтобы фабрика аллоцировала
правильное число имён.

Если нужна одна конкретная точка из нескольких пересечений, используйте
1-based индекс: `p = Intersect(c, L, index=1)` или позиционно
`p = Intersect(c, L, 1)`.

Порядок пересечений является частью публичного контракта. Первый элемент
tuple-unpack соответствует `Intersect(..., index=1)`, второй —
`Intersect(..., index=2)` и так далее. Для окружностей используется
GeoGebra-like эвристика: если окружность построена по уже известным точкам,
то совпадающие с ними точки пересечения идут первыми в порядке входов
окружности, затем учитываются точки второго входного объекта, а оставшиеся
пересечения сохраняют внутренний детерминированный порядок. Этот порядок
должен оставаться одинаковым для `.ggb` import, Python DSL и путей
экспорта/JSXGraph.

## Доступ к полям

Через прокси (что возвращает фабрика):

```python
A = Point(3, 4)
print(A.x, A.y)           # 3.0, 4.0
print(A.coords)           # [3., 4.]

circ = Circle(Point(0, 0), 5)
print(circ.center)        # [0., 0.]
print(circ.radius)        # 5

s = Segment(Point(0, 0), Point(3, 4))
print(s.start, s.end, s.length)
```

Полный список — `docs/field_names.md`.

Чтение происходит «живым» — после любого `dsl.run` поля отражают
актуальное состояние.

## Стили

`elem.style` — теперь `StyleProxy` (subclass от `dict`). Оба API
работают одновременно.

### Атрибутный (новый)

```python
A = Point(3, 4)
A.style.stroke = "#ff0000"
A.style.size_px = 12
A.style.label_visible = True
```

### Словарный (legacy — ничего не сломалось)

```python
A.style["stroke"] = "#ff0000"
A.style.get("stroke", "black")
"stroke" in A.style
for k, v in A.style.items(): ...
json.dumps(A.style)           # всё ещё работает
```

### Batch-хелперы

```python
style(A, B, C, stroke="#f00", size=10)
hide(A, B)
show(C)
```

Missing-attr возвращает `None` (не `AttributeError`), mirroring CSS
semantic: `if A.style.stroke:` — «стиль задан?».

## Что запрещено

`DSLSyntaxError` на этапе transform с line/col:

- `import module` / `from module import name`
- `global x` / `nonlocal x`
- `A += expr` (augmented assignment)
- `(A := expr)` (walrus)
- `A: int = 5` (annotated assignment с value)
- `A = B = expr` (chained assignment)
- Имена с leading underscore для LHS (зарезервированы под phantoms)

`NameError` в runtime:
- `open`, `eval`, `exec`, `__import__`, `compile` — не в sandbox

## Что умеет exec-движок

- `for`, `if`, `while`, `def`, comprehensions, lambda — как в Python
- `**kwargs` в фабриках (`Point(3, 4, name='A')`)
- Неизвестная CamelCase-команда → `NameError` (чёткое сообщение)
- Повторное присвоение в одном scope → обновляет, в цикле/def → автоуникализация `name_2, name_3, …`
- Доступ к полям через прокси (`A.x`, `A.y`, `circ.center`, `seg.length`)
- Стили атрибутом: `A.style.stroke = '#f00'`
- f-строки, tuple-unpack (`a, b = Intersect(c, l)`), арифметика на прокси (`A - B → Sub-команда`)
- Forward-ref для lowercase имён: `B = Rotate(R, x*deg, Q)` работает, даже если `x` ещё не определён (его задаст `scene.addVar('x', 115)` позже)

## Текущие ограничения

- `.pyi` стабы покрывают ~30 детальных сигнатур + 44 generic; для редко используемых команд IDE может показывать `Any` вместо точного типа. Расширить можно в `namespace.pyi` (запускаемый валидатор: `python3 -m animageo.parsers.dsl._regen_stubs`).
- Sandbox: `open`, `eval`, `exec`, `__import__`, `compile` заблокированы — в runtime `NameError`. Top-level `import` silently dropped (оставляет место для IDE-stubs, но имя в runtime не bind'ится).
