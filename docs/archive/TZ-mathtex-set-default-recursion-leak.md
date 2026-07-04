# ТЗ: `MathTex.set_default(color=…)` в applyStyle накапливает partialmethod-цепочку → RecursionError после ~1000 рендеров в одном процессе

**Кому:** команде разработки библиотеки `animageo`
**Модуль:** `animageo/animageo.py` (`applyStyle`, строка ~1003: `MathTex.set_default(color = self.style.strong)`)
**Версия, на которой проводился анализ:** `animageo == 1.4.3`, `manim == 0.20.1`, Python 3.13
**Приоритет:** высокий (тихо ломает рендер подписей у ВСЕХ конструкций в долгоживущем процессе; в animageo-web «съедает» точки и подписи в превью)
**Автор разбора:** диагностика по обращению владельца сервиса animageo-web

---

## 1. Краткая суть

`applyStyle()` на каждом вызове (то есть на каждом `loadGGB`/рендере) делает:

```python
MathTex.set_default(color = self.style.strong)   # animageo/animageo.py:~1003
```

manim реализует `set_default` так (manim/mobject/mobject.py):

```python
@classmethod
def set_default(cls, **kwargs):
    if kwargs:
        cls.__init__ = partialmethod(cls.__init__, **kwargs)   # ← оборачивает ТЕКУЩИЙ __init__
    else:
        cls.__init__ = cls._original__init__
```

Казалось бы, `functools.partialmethod` «сплющивает» вложенные partialmethod. Но **не здесь**: выражение `cls.__init__` при чтении с класса срабатывает через дескриптор `partialmethod.__get__` и возвращает **функцию `_method`**, а не сам объект `partialmethod`. Поэтому `partialmethod(cls.__init__, **kwargs)` оборачивает функцию (не partialmethod) → **флаттенинга не происходит, добавляется новый слой на каждый вызов.**

Итог: каждый `set_default(color=…)` увеличивает глубину цепочки `MathTex.__init__` на 1. Конструирование любого `MathTex`/`Tex` тогда рекурсивно проходит всю цепочку. Когда глубина превышает `sys.getrecursionlimit()` (по умолчанию 1000) — **любой рендер подписи падает с `RecursionError`.**

## 2. Воспроизведение (изолированно, без полного рендера)

```python
import functools
from manim import MathTex

def chain_len(cls):
    init = cls.__dict__.get('__init__'); n = 0
    while isinstance(init, functools.partialmethod):
        n += 1
        pm = getattr(init.func, '__partialmethod__', None)
        if pm is None: break
        init = pm
    return n

print(chain_len(MathTex))            # 0
for i in range(10):
    MathTex.set_default(color="#444444")   # == один applyStyle / один рендер
    print(chain_len(MathTex))         # 1,2,3,...,10  — растёт линейно
# после ~1000 вызовов: MathTex("x") → RecursionError: maximum recursion depth exceeded
```

## 3. Как это проявляется в проде (ground truth)

Сервис animageo-web рендерит **живое превью в самом процессе FastAPI-приложения** (долгоживущий процесс). Экспорт же идёт в **свежих Celery-воркерах** (новый процесс на задачу). Поэтому цепочка растёт именно в app-процессе, и после ~1000 превью-рендеров **все подписи начинают падать**.

Реальный трейс из прод-логов (конструкция https://animageo.ru/shared/tYwHUgEyock, превью):

```
WARNING animageo: CreateMObject failed for "Q" (Point): maximum recursion depth exceeded
  animageo/animageo.py:2536  _render_point → arr.append(self._make_label(elem, pos, ctx))
  animageo/animageo.py:2040  _make_label → create_label(...)
  animageo/ui.py:327  create_label → Tex(correctedLabel(label), color=col_label).set(font_size=…, tex_template=RusTex)
  manim/mobject/text/tex_mobject.py:631  __init__ → super().__init__
  functools.py:402  _method → return self.func(cls_or_self, ...)
  [Previous line repeated 983 more times]
RecursionError: maximum recursion depth exceeded
```

`_render_point`/`_render_angle` ловят исключение по-элементно и **пропускают весь элемент** — в результате исчезают И маркеры точек, И подписи. Остаётся только геометрия без подписей (в примере: 15 `<path>` вместо 35). Тот же `.ggb`, отрендеренный в свежем процессе, даёт полные 35 `<path>`.

> ⚠️ Это **бомба замедленного действия и для экспорта тоже**: Celery-воркеры — тоже долгоживущие процессы. Каждый экспорт (`applyStyle`) добавляет слой; после ~1000 задач на воркере подписи начнут падать и в экспорте, пока воркер не пересоздастся. (Веб со своей стороны может смягчить это `--max-tasks-per-child` и перезапуском app-процесса, но корень — здесь.)

## 4. Корневая причина

`applyStyle` мутирует **глобальное состояние класса manim** (`MathTex.__init__`) на каждом вызове, без сброса, и manim-овский `set_default` в этом сценарии не идемпотентен (накапливает partialmethod). Дополнительный риск: это **глобальная мутация класса**, небезопасная при конкурентных рендерах в тредах (гонка за `MathTex.__init__`).

## 5. Рекомендуемое исправление

Любой из вариантов (по возрастанию надёжности):

1. **Сбрасывать перед установкой** — сделать вызов идемпотентным:
   ```python
   MathTex.set_default()                    # вернуть оригинальный __init__
   MathTex.set_default(color=self.style.strong)
   ```
   Глубина цепочки всегда ≤ 1. Минимальная правка. (Но глобальная мутация класса остаётся — см. п.3 о тредобезопасности.)

2. **Не использовать `set_default` вообще** (предпочтительно). Цвет подписи и так передаётся явно в `create_label` (`Tex(..., color=col_label)`). Найти места, где `MathTex`/`Tex` создаётся без явного `color`, и передавать цвет туда напрямую; строку `MathTex.set_default(color=…)` убрать. Это устраняет и накопление, и глобальную гонку.

3. Если глобальный дефолт всё же нужен — ставить его **один раз** (при инициализации, не в `applyStyle`), и/или оборачивать рендер в `try/finally` со сбросом.

## 6. Критерии приёмки

1. После N применений стиля/рендеров в одном процессе `chain_len(MathTex)` (см. §2) остаётся ограниченной (≤1), не растёт линейно с числом рендеров.
2. 2000+ последовательных рендеров конструкции с подписями в одном процессе не приводят к `RecursionError`; подписи и точки присутствуют на каждом.
3. Цвет подписей остаётся прежним (регресс визуально не меняет вывод).
4. (Желательно) рендер потокобезопасен: одновременные рендеры разных стилей в тредах не мешают друг другу через глобальный `MathTex.__init__`.

## 7. Приложения

- `.ggb`: `GET https://animageo.ru/api/shared/tYwHUgEyock/ggb`.
- Симптом в animageo-web: превью конструкции теряет все точки и подписи (только геометрия), тогда как экспорт того же кадра их содержит; перезапуск app-контейнера временно чинит превью (сбрасывает процесс).
