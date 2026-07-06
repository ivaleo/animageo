# Fix: `RecursionError: maximum recursion depth exceeded` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить все известные источники `RecursionError` в animageo: (1) накопление `functools.partialmethod`-цепочки на `MathTex/Text/MarkupText.__init__` из-за `set_default` в `applyStyle` (ТЗ: `docs/archive/TZ-mathtex-set-default-recursion-leak.md`), (2) неограниченную рекурсию при разворачивании циклических GGB-макросов, (3) добавить диагностическую подсказку в per-element recovery, чтобы будущие RecursionError не выглядели как поэлементные баги.

**Architecture:** Для (1) — вариант 2 из ТЗ (предпочтительный): полностью удалить три вызова `set_default` из `AnimaGeoScene.setStyle` (animageo/animageo.py:1002–1004). Основной путь рендера подписей (`_build_render_ctx` → `col_label` → `create_label` → `Tex(..., color=col_label)`) уже передаёт цвет явно и от глобального дефолта не зависит (проверено экспериментально). Единственный потребитель глобального дефолта во всём пакете — `ShowText` в `animageo/ui.py:412,419`: туда цвет передаётся явно ДО удаления `set_default`, чтобы не было промежуточной регрессии. Это также закрывает пункт ТЗ §6.4 о тредобезопасности: глобальная мутация класса исчезает полностью. Для (2) — хирургический guard глубины в `expand_macros_in_construction` (лимит проходов + warning, неразвёрнутые вызовы остаются и попадают в существующую диагностику unsupported-команд). Для (3) — одна ветка в существующем catch-блоке `CreateMObject`.

**Tech Stack:** Python 3.13 (homebrew), manim 0.20.1, pytest.

## Global Constraints

- Тесты запускать через `python3.13 -m pytest ...` (системный `python3` = 3.14 без manim; см. docs/gotchas.md).
- Версии из ТЗ: `animageo == 1.4.3`, `manim == 0.20.1`, Python 3.13.
- Критерии приёмки ТЗ §6: (1) `chain_len(MathTex)` ограничена (у нас — ровно 0) после N применений стиля; (2) 2000+ рендеров в одном процессе без `RecursionError`; (3) цвет подписей визуально не меняется; (4) желательно — тредобезопасность.
- Визуальный вывод основного пути рендера (SVG/MP4/TikZ/JSXGraph) должен остаться байт-в-байт прежним — проверяется полным прогоном тестов.
- Коммиты БЕЗ AI-attribution трейлеров (Co-Authored-By и т.п.) — правило проекта.
- LaTeX-тулчейн в dev-окружении есть (существующие тесты, напр. `tests/test_value_labels.py`, уже компилируют Tex без skip-guard).

## Расследование: все источники RecursionError (проверено на живом коде)

**Источник 1 — partialmethod-утечка `set_default` (корневая причина ТЗ).** Одна причина объясняет РАЗНЫЕ на вид симптомы, потому что после переполнения цепочки падает КАЖДОЕ конструирование Tex-подобного мобжекта:

| Место падения | Симптом |
|---|---|
| `_render_point`/`_render_angle`/все `_render_*` → `_make_label` → `create_label` → `Tex(...)` | per-element `except Exception` (animageo.py:2785) ловит → элемент молча выпадает целиком (исчезают И точки, И подписи — прод-кейс из ТЗ §3) |
| `label_placement._measure_label_bbox` → `Tex(...)` (label_placement.py:75) | НЕ обёрнуто per-element → `RecursionError` пролетает вверх, `autoPlaceLabels`/`compute_label_layout` падает целиком (другой симптом, та же причина) |
| `ValueLabel`/`DecimalNumber` — в manim 0.20 `DecimalNumber(mob_class=MathTex)` по умолчанию | «быстрые» value-подписи и `prewarm_decimal_glyphs` тоже идут через патченный `MathTex.__init__` → падают анимации `play_keyframes`/`addUpdater` |
| `Text` (оси animageo.py:1789, error-rect :369, `NumberedFrame`/`FixedLabel`), `ShowText` | `Text.set_default` рос той же цепочкой (setStyle патчил и его) |

Вывод: задачи 1–2 закрывают ВСЕ эти ситуации разом.

**Источник 2 — циклические GGB-макросы (независимый, воспроизведён).** `expand_macros_in_construction` (parsers/ggb_macro.py:236–240) рекурсивно вызывает себя, пока в конструкции остаются макро-вызовы, БЕЗ ограничения глубины. Макрос, чьё тело вызывает его же (напрямую или взаимно A→B→A) в `geogebra_macro.xml`, даёт ~1000 проходов → `RecursionError` прямо в `loadGGB`. Репро подтверждено на текущем коде минимальным XML (см. тест в Task 3). Это user-triggerable через загрузку .ggb в animageo-web. Легитимная вложенность (макрос зовёт другой макрос) — глубина проходов = уровню вложенности, на практике 2–5.

**Проверено и признано НЕ источниками (не трогаем):**
- `Element.__getattr__` (geo/lib_elements.py:71), `ElementProxy.__getattr__` (parsers/dsl/proxy.py:100) — корректно защищены (guard на `_`-атрибуты, чтение через `self.__dict__.get`).
- `curve_sampling.sample_parametric` — итеративный `while` с жёстким капом `max_samples`.
- `Construction.rebuild` — итеративные циклы (Kahn), без рекурсии.
- `svg_parser`, экспортёры tikz/jsxgraph — плоские обходы.
- Препроцессор `If[...]` → `Piecewise` (lib_function.py:119) и sympy/ast-парсинг — глубина рекурсии = глубине вложенности выражения; патологический ввод (сотни вложенных скобок/If) может уронить сам sympy/CPython-парсер. Это неотъемлемое свойство любых парсеров; лечится catch'ем на входной точке сервиса (animageo-web), не библиотекой. Out of scope, зафиксировано здесь.

## Прочие проверенные факты (контекст для исполнителя)

- `manim.Mobject.set_default(**kwargs)` делает `cls.__init__ = partialmethod(cls.__init__, **kwargs)`; чтение `cls.__init__` идёт через дескриптор и возвращает функцию `_method`, поэтому флаттенинга нет — каждый вызов добавляет слой. `set_default()` без аргументов восстанавливает `cls._original__init__` (обычную функцию). Проверено: 5 × `scene.applyStyle()` → цепочка глубиной 5 у всех трёх классов.
- Явный `color=` в вызове всегда побеждает partialmethod-дефолт, поэтому основной путь подписей цвет не менял и не поменяет.
- У `Tex`, созданного с явным `color=`, верхний `get_fill_color()` возвращает `None` — реальный цвет глифов читать через `family_members_with_points()` (проверено: подпись точки → все листья `#000000`).
- Текущий `ShowText` без активного глобального дефолта рендерит body БЕЛЫМ (`#FFFFFF`), а с дефолтом — `style.strong` (`#000000`); header визуально задаётся через `set_fill(scene.style.col)` и от дефолта не зависит.
- `MarkupText` нигде в пакете не конструируется — его `set_default` был чистой мёртвой глобальной мутацией. `Text` конструируется только с явным цветом (animageo.py:369, 1789; ui.py:444, 474). `Tex` в `label_placement.py:75` — только для измерения bbox, цвет не важен.

## Out of scope (зафиксировать, не делать)

- `examples/main.py` содержит свои копии `setStyle` с `set_default` — это one-shot скрипты (свежий процесс на рендер), в пакет не входят; не трогаем.
- В `ShowText` есть pre-existing баг алиасинга: `pos += 0.7 * DOWN` мутирует переданный массив (включая манимовский `ORIGIN` при дефолтном значении). Замечен, не чиним в этой задаче; в тестах передавать явный `pos=np.array([...])`.
- Никаких «защитных» вызовов `MathTex.set_default()` (сброса) в библиотеке не добавляем: это снова глобальная мутация, затирающая пользовательские дефолты.
- Глубокая вложенность выражений в sympy/ast-парсерах (см. раздел расследования) — лечится на входной точке animageo-web, не здесь.

## File Structure

- Modify: `animageo/ui.py:411-419` — `ShowText`: явный `color=` у обоих `Tex` (Task 1)
- Create: `tests/test_show_text_colors.py` (Task 1)
- Modify: `animageo/animageo.py:998-1004` — `setStyle`: удалить три `set_default` (Task 2)
- Create: `tests/test_mobject_default_leak.py` (Task 2, дополняется в Task 4)
- Modify: `animageo/parsers/ggb_macro.py` — лимит глубины разворачивания макросов (Task 3)
- Modify: `tests/test_ggb_macro.py` — фикстура + тест циклического макроса (Task 3)
- Modify: `animageo/animageo.py:2785-2793` — диагностическая подсказка при RecursionError в `CreateMObject` (Task 4)
- Modify: `docs/gotchas.md` — новая запись в разделе `## manim` (Task 5)
- Modify: `CHANGELOG.md` — секция `[Unreleased] / Fixed` (Task 5)

---

### Task 1: `ShowText` — явные цвета вместо глобального дефолта

Единственное место в пакете, полагающееся на `MathTex.set_default(color=strong)`. Передаём цвет явно СНАЧАЛА, чтобы удаление `set_default` в Task 2 ничего визуально не сломало.

**Files:**
- Modify: `animageo/ui.py:411-419`
- Test: `tests/test_show_text_colors.py`

**Interfaces:**
- Consumes: `animageo.ui.ShowText(scene, header, body, pos, ...)`, `animageo.style.GeoStyle` (атрибуты `.strong` = `BLACK`, `.col` = `#6688C2` по умолчанию).
- Produces: поведение `ShowText` не зависит от классовых дефолтов manim; body-текст всегда `scene.style.strong`, header-заливка всегда `scene.style.col`. Сигнатура `ShowText` не меняется.

- [ ] **Step 1: Написать падающий тест**

Создать `tests/test_show_text_colors.py`:

```python
"""ShowText must not depend on manim class-level default colours.

Part of the MathTex.set_default leak fix (docs/TZ-mathtex-set-default-
recursion-leak.md): after the set_default calls are removed from
AnimaGeoScene.setStyle, every Tex in the package must receive its colour
explicitly. ShowText's body Tex was the only consumer of the class default
(it rendered strong-coloured only because setStyle had previously mutated
MathTex.__init__ globally).
"""
import numpy as np
import pytest
from manim import ManimColor, MarkupText, MathTex, Text

from animageo.style import GeoStyle
from animageo.ui import ShowText

_CLASSES = (Text, MathTex, MarkupText)


@pytest.fixture(autouse=True)
def _reset_manim_class_defaults():
    """Isolate from any set_default made elsewhere in the test session."""
    for cls in _CLASSES:
        cls.set_default()
    yield
    for cls in _CLASSES:
        cls.set_default()


class _StubScene:
    """Minimal stand-in: ShowText only touches scene.style and scene.play."""

    def __init__(self):
        self.style = GeoStyle()
        self.played = []

    def play(self, *anims, **kwargs):
        self.played.extend(anims)


def _leaf_fills(mobj):
    return {m.get_fill_color().to_hex() for m in mobj.family_members_with_points()}


class TestShowTextColors:
    def test_body_uses_style_strong(self):
        scene = _StubScene()
        ShowText(scene, header=None, body='Тело', pos=np.array([0.0, 0.0, 0.0]))
        (anim,) = scene.played
        expected = ManimColor(scene.style.strong).to_hex()
        assert _leaf_fills(anim.mobject) == {expected}

    def test_header_keeps_style_col_fill(self):
        scene = _StubScene()
        ShowText(scene, header='Заголовок', body=None, pos=np.array([0.0, 0.0, 0.0]))
        (anim,) = scene.played
        expected = ManimColor(scene.style.col).to_hex()
        assert _leaf_fills(anim.mobject) == {expected}
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `python3.13 -m pytest tests/test_show_text_colors.py -v`
Expected: `test_body_uses_style_strong` FAIL — леса body белые (`{'#FFFFFF'}`), а не `{'#000000'}` (фикстура сбросила классовые дефолты, а в свежем pytest-процессе `setStyle` для этой сцены и не вызывался — виден «голый» дефолт manim). `test_header_keeps_style_col_fill` PASS (header красится через `set_fill`).

- [ ] **Step 3: Передать цвет явно в `ShowText`**

В `animageo/ui.py` заменить (строки 411–419):

```python
    if header:
        theader = Tex(header, font_size=37, tex_template=RusTex)
        theader.set_fill(color=scene.style.col)
```

на:

```python
    if header:
        theader = Tex(header, font_size=37, tex_template=RusTex,
                      color=scene.style.strong)
        theader.set_fill(color=scene.style.col)
```

и:

```python
    if body:
        tbody = Tex(body, font_size=34, tex_template=RusTex)
```

на:

```python
    if body:
        tbody = Tex(body, font_size=34, tex_template=RusTex,
                    color=scene.style.strong)
```

(header: `color=strong` воспроизводит то, что раньше давал глобальный дефолт на момент `__init__`; заливка, как и прежде, перекрывается `set_fill(col)` — визуально байт-в-байт.)

- [ ] **Step 4: Убедиться, что тест проходит**

Run: `python3.13 -m pytest tests/test_show_text_colors.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_show_text_colors.py animageo/ui.py
git commit -m "fix(ui): pass explicit colors in ShowText instead of manim class defaults"
```

---

### Task 2: Удалить `set_default` из `setStyle` + регрессионные тесты на утечку

Собственно фикс ТЗ: `setStyle` перестаёт мутировать глобальное состояние классов manim. Цепочка `__init__` больше не растёт вовсе (глубина 0 < требуемого ТЗ «≤ 1»), исчезает и гонка между тредами (§6.4). Разом закрываются ВСЕ симптомы источника 1 из таблицы расследования (подписи элементов, label placement, value-подписи, оси).

**Files:**
- Modify: `animageo/animageo.py:998-1004` (`setStyle`)
- Test: `tests/test_mobject_default_leak.py`

**Interfaces:**
- Consumes: `AnimaGeoScene()` (без аргументов), `scene.applyStyle()` (без аргументов — builtin-стиль), `scene.setStyle(scene.style)`, `scene.putCode(str)`, `scene.addAllGeometry(show=True)`, `scene.mobject(name)`.
- Produces: `setStyle(style)` только присваивает `self.style` и `camera.background_color`; классы `Text/MathTex/MarkupText` не трогает. Никакой новый API не появляется. Тестовый файл `tests/test_mobject_default_leak.py` с фикстурой `_reset_manim_class_defaults` и классом `TestSetDefaultLeak` — Task 4 добавит в этот же файл класс `TestRecursionErrorDiagnostics`.

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_mobject_default_leak.py`:

```python
"""Regression: AnimaGeoScene.setStyle must not mutate manim class defaults.

manim's Mobject.set_default wraps the CURRENT cls.__init__ in a fresh
functools.partialmethod on every call: reading cls.__init__ off the class
goes through the partialmethod descriptor and returns the compiled _method
function, so nested partialmethods never flatten. Repeated applyStyle calls
therefore grew MathTex/Text/MarkupText.__init__ by one layer each, and after
~1000 renders in one long-lived process every label construction died with
RecursionError (docs/archive/TZ-mathtex-set-default-recursion-leak.md).
"""
import functools

import pytest
from manim import ManimColor, MarkupText, MathTex, Tex, Text

from animageo.animageo import AnimaGeoScene

_CLASSES = (Text, MathTex, MarkupText)


def _chain_len(cls):
    """Depth of the partialmethod chain around cls.__init__ (ТЗ §2)."""
    init = cls.__dict__.get('__init__')
    n = 0
    while isinstance(init, functools.partialmethod):
        n += 1
        pm = getattr(init.func, '__partialmethod__', None)
        if pm is None:
            break
        init = pm
    return n


@pytest.fixture(autouse=True)
def _reset_manim_class_defaults():
    """Restore pristine __init__ before and after each test."""
    for cls in _CLASSES:
        cls.set_default()
    yield
    for cls in _CLASSES:
        cls.set_default()


class TestSetDefaultLeak:
    def test_apply_style_does_not_grow_init_chain(self):
        """ТЗ §6.1: chain depth stays bounded (== 0) across style applies."""
        scene = AnimaGeoScene()
        for _ in range(50):
            scene.applyStyle()
        for cls in _CLASSES:
            assert _chain_len(cls) == 0, cls.__name__

    def test_tex_constructible_after_more_applies_than_recursion_limit(self):
        """ТЗ §6.2 proxy: more setStyle calls than sys.getrecursionlimit()
        (default 1000) must leave MathTex constructible. Before the fix this
        was exactly the state that raised RecursionError on every label."""
        scene = AnimaGeoScene()
        scene.applyStyle()
        for _ in range(1200):
            scene.setStyle(scene.style)
        for cls in _CLASSES:
            assert _chain_len(cls) == 0, cls.__name__
        MathTex("1")  # must not raise RecursionError

    def test_point_label_color_unchanged(self):
        """ТЗ §6.3: label colour still comes out presets.color.strong —
        the render path passes col_label explicitly, no global default
        needed. Passes before AND after the fix (regression lock)."""
        scene = AnimaGeoScene()
        scene.putCode("""
A = Point(1, 1)
A.style.label_visible = True
""")
        scene.applyStyle()
        scene.addAllGeometry(show=True)
        labels = [m for m in scene.mobject('A').submobjects
                  if isinstance(m, Tex)]
        assert labels, "point label missing"
        expected = ManimColor(scene.style.strong).to_hex()
        leaf_fills = {m.get_fill_color().to_hex()
                      for m in labels[0].family_members_with_points()}
        assert leaf_fills == {expected}
```

- [ ] **Step 2: Убедиться, что тесты падают как ожидается**

Run: `python3.13 -m pytest tests/test_mobject_default_leak.py -v`
Expected:
- `test_apply_style_does_not_grow_init_chain` FAIL — `_chain_len == 50`;
- `test_tex_constructible_after_more_applies_than_recursion_limit` FAIL — assert глубины цепочки сработает первым (`_chain_len == 1201`, а не 0); до `MathTex("1")` тест не дойдёт;
- `test_point_label_color_unchanged` PASS (лок текущего корректного поведения).

- [ ] **Step 3: Удалить `set_default` из `setStyle`**

В `animageo/animageo.py` заменить (строки 998–1004):

```python
    def setStyle(self, style):
        self.style = style

        self.camera.background_color = self.style.background
        Text.set_default(color = self.style.strong)
        MathTex.set_default(color = self.style.strong)
        MarkupText.set_default(color = self.style.strong)
```

на:

```python
    def setStyle(self, style):
        self.style = style

        self.camera.background_color = self.style.background
        # Never call Text/MathTex/MarkupText.set_default here: manim wraps the
        # *current* __init__ in a new functools.partialmethod on every call
        # (no flattening), so per-render calls grew the chain until any label
        # hit RecursionError after ~1000 renders in one process. Label colour
        # is always passed explicitly (col_label in _build_render_ctx).
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `python3.13 -m pytest tests/test_mobject_default_leak.py tests/test_show_text_colors.py -v`
Expected: 5 passed (три новых + два из Task 1 — `ShowText` больше не зависит от удалённого дефолта).

- [ ] **Step 5: Прогнать смежные рендер-тесты (быстрая проверка регрессий цвета)**

Run: `python3.13 -m pytest tests/test_value_labels.py tests/test_create_mobject_dispatch.py tests/test_conic_render.py tests/test_dsl_angle_defaults.py -q`
Expected: all passed (основной путь рендера цвет получал явно и не изменился).

- [ ] **Step 6: Commit**

```bash
git add tests/test_mobject_default_leak.py animageo/animageo.py
git commit -m "fix(render): drop MathTex/Text/MarkupText set_default from setStyle

manim's Mobject.set_default wraps the current __init__ in a new
partialmethod on every call, so per-applyStyle calls grew the chain by one
layer per render; after ~1000 renders in a long-lived process (animageo-web
preview, Celery workers) every label construction failed with
RecursionError and points/labels silently vanished from output. The label
render path passes colour explicitly (col_label), so the global default was
only consumed by ShowText, fixed in the previous commit."
```

---

### Task 3: Лимит глубины разворачивания GGB-макросов (циклический макрос ≠ RecursionError)

Независимый источник RecursionError, найденный при расследовании и воспроизведённый: `expand_macros_in_construction` рекурсивно зовёт себя, пока остаются макро-вызовы, без ограничения. Циклический макрос в `geogebra_macro.xml` (тело вызывает сам себя, напрямую или взаимно) валит `loadGGB` с `RecursionError` после ~1000 проходов. Хирургический фикс: параметр `_depth` + кап; при превышении — warning, неразвёрнутые вызовы остаются в дереве и дальше попадают в штатную диагностику unsupported-команд (`construction.command_diagnostics`).

**Files:**
- Modify: `animageo/parsers/ggb_macro.py` (константа + сигнатура + guard + рекурсивный вызов)
- Test: `tests/test_ggb_macro.py` (добавить фикстуру и тест-класс в конец файла)

**Interfaces:**
- Consumes: `parse_macros(root) -> dict[str, Macro]`, `expand_macros_in_construction(constr_xelem, macros)` — существующие публичные функции модуля.
- Produces: `MAX_MACRO_EXPANSION_PASSES: int = 32` (модульная константа `ggb_macro.py`); сигнатура получает приватный параметр `_depth: int = 0` — внешние вызовы (ggb_parser.py, тесты) не меняются.

- [ ] **Step 1: Написать падающий тест**

В конец `tests/test_ggb_macro.py` добавить (и добавить `import logging` к импортам в шапке файла, после `import os`):

```python
# ── Cyclic macro guard ────────────────────────────────────────────────

@pytest.fixture
def cyclic_macro_xml():
    """A macro whose body calls itself — malformed, but must not blow the
    stack (RecursionError) or hang; leftover calls go to the
    unsupported-command diagnostics instead."""
    return ET.fromstring("""
    <geogebra>
        <macro cmdName="Loop" toolName="Loop">
            <macroInput a0="P" a1="Q"/>
            <macroOutput a0="R"/>
            <construction>
                <command name="Loop">
                    <input a0="P" a1="Q"/>
                    <output a0="R"/>
                </command>
            </construction>
        </macro>
    </geogebra>
    """)


class TestCyclicMacroGuard:
    def test_cyclic_macro_terminates_without_recursion_error(
            self, cyclic_macro_xml, caplog):
        macros = parse_macros(cyclic_macro_xml)
        constr = ET.fromstring("""
        <construction>
            <command name="Loop">
                <input a0="A" a1="B"/>
                <output a0="C"/>
            </command>
        </construction>
        """)
        with caplog.at_level(logging.WARNING,
                             logger="animageo.parsers.ggb_macro"):
            expand_macros_in_construction(constr, macros)

        # Terminated: exactly one unexpandable call left in place.
        leftover = [c for c in constr.findall("command")
                    if c.attrib.get("name") == "Loop"]
        assert len(leftover) == 1
        assert any("did not converge" in r.getMessage()
                   for r in caplog.records)
```

- [ ] **Step 2: Убедиться, что тест падает**

Run: `python3.13 -m pytest tests/test_ggb_macro.py::TestCyclicMacroGuard -v`
Expected: FAIL с `RecursionError: maximum recursion depth exceeded` (воспроизведено на текущем коде именно этим XML).

- [ ] **Step 3: Добавить guard глубины**

В `animageo/parsers/ggb_macro.py`:

1. После строки `logger = logging.getLogger(__name__)` (шапка модуля) добавить:

```python
# One expansion pass rewrites every macro call currently present; legit
# nested macros need one pass per nesting level (real files: 2-5). A cyclic
# macro (whose body calls itself, directly or mutually) would never
# converge, so expansion stops after this many passes and the remaining
# calls surface through the unsupported-command diagnostics.
MAX_MACRO_EXPANSION_PASSES = 32
```

2. Сигнатуру функции (строки 141–145) заменить:

```python
def expand_macros_in_construction(
    constr_xelem: ET.Element,
    macros: dict[str, Macro],
    _call_counter: dict[str, int] | None = None,
) -> None:
```

на:

```python
def expand_macros_in_construction(
    constr_xelem: ET.Element,
    macros: dict[str, Macro],
    _call_counter: dict[str, int] | None = None,
    _depth: int = 0,
) -> None:
```

3. Сразу после docstring (перед `if _call_counter is None:`) добавить:

```python
    if _depth >= MAX_MACRO_EXPANSION_PASSES:
        leftover = sorted({
            c.attrib.get("name", "")
            for c in constr_xelem.findall("command")
            if c.attrib.get("name", "") in macros
        })
        logger.warning(
            "Macro expansion did not converge after %d passes — cyclic "
            "macro definition? Leaving calls unexpanded: %s",
            MAX_MACRO_EXPANSION_PASSES, ", ".join(leftover),
        )
        return
```

4. Рекурсивный вызов в хвосте функции (строка ~240) заменить:

```python
        expand_macros_in_construction(constr_xelem, macros, _call_counter)
```

на:

```python
        expand_macros_in_construction(constr_xelem, macros, _call_counter,
                                      _depth + 1)
```

- [ ] **Step 4: Убедиться, что тесты проходят (новый + все существующие макро-тесты)**

Run: `python3.13 -m pytest tests/test_ggb_macro.py -v`
Expected: all passed — легитимная вложенность (`nested_macro_xml`, pict.ggb integration) не задета (глубина проходов ≤ 32), циклический макрос завершается с warning.

- [ ] **Step 5: Commit**

```bash
git add tests/test_ggb_macro.py animageo/parsers/ggb_macro.py
git commit -m "fix(parser): cap macro expansion passes so cyclic macros can't hit RecursionError

expand_macros_in_construction recursed once per pass with no bound, so a
geogebra_macro.xml whose macro body calls itself (directly or mutually)
crashed loadGGB with RecursionError after ~1000 passes. Expansion now stops
after MAX_MACRO_EXPANSION_PASSES (32) with a warning; the unexpanded calls
flow into the existing unsupported-command diagnostics."
```

---

### Task 4: Диагностическая подсказка при RecursionError в per-element recovery

`RecursionError` в `CreateMObject` — никогда не поэлементная проблема: это признак порчи process-wide состояния (например, накопленной partialmethod-цепочки со стороны пользовательского кода). Сегодня он тонет в общем WARNING и выглядит как баг элемента — прод-кейс ТЗ расследовали вслепую. Добавляем подсказку в лог.

**Files:**
- Modify: `animageo/animageo.py:2785-2793` (catch-блок `CreateMObject`)
- Test: `tests/test_mobject_default_leak.py` (добавить класс в конец файла)

**Interfaces:**
- Consumes: `AnimaGeoScene.CreateMObject(elem)` и его catch-блок; фикстура `_reset_manim_class_defaults` и импорты уже есть в тестовом файле из Task 2.
- Produces: формат лога расширяется только при `isinstance(e, RecursionError)`; возвращаемое значение (`None` при ошибке) и поведение для остальных исключений не меняются.

- [ ] **Step 1: Написать падающий тест**

В конец `tests/test_mobject_default_leak.py` добавить (и добавить `import logging` к импортам в шапке файла, после `import functools`):

```python
class TestRecursionErrorDiagnostics:
    def test_recursion_error_render_failure_logs_root_cause_hint(
            self, caplog, monkeypatch):
        """A RecursionError caught by per-element recovery must point at the
        process-wide root cause instead of reading like an element bug."""
        scene = AnimaGeoScene()
        scene.putCode("A = Point(1, 1)")
        elem = scene.geo.element('A')

        def _boom(elem, z_auto):
            raise RecursionError('maximum recursion depth exceeded')

        monkeypatch.setattr(scene, '_build_render_ctx', _boom)
        with caplog.at_level(logging.WARNING, logger='animageo.animageo'):
            result = scene.CreateMObject(elem)

        assert result is None
        assert any('set_default' in r.getMessage()
                   and 'gotchas' in r.getMessage()
                   for r in caplog.records)

    def test_ordinary_render_failure_has_no_recursion_hint(
            self, caplog, monkeypatch):
        scene = AnimaGeoScene()
        scene.putCode("A = Point(1, 1)")
        elem = scene.geo.element('A')

        def _boom(elem, z_auto):
            raise ValueError('plain element failure')

        monkeypatch.setattr(scene, '_build_render_ctx', _boom)
        with caplog.at_level(logging.WARNING, logger='animageo.animageo'):
            result = scene.CreateMObject(elem)

        assert result is None
        assert not any('set_default' in r.getMessage()
                       for r in caplog.records)
```

- [ ] **Step 2: Убедиться, что первый тест падает**

Run: `python3.13 -m pytest tests/test_mobject_default_leak.py::TestRecursionErrorDiagnostics -v`
Expected: `test_recursion_error_render_failure_logs_root_cause_hint` FAIL (в логе нет подсказки), `test_ordinary_render_failure_has_no_recursion_hint` PASS.

- [ ] **Step 3: Добавить подсказку в catch-блок**

В `animageo/animageo.py` заменить (строки 2785–2793):

```python
        except Exception as e:
            logger.warning(
                'CreateMObject failed for "%s" (%s): %s\n%s',
                elem.name,
                type(elem.data).__name__ if elem.data else 'None',
                e,
                traceback.format_exc(),
            )
            return None
```

на:

```python
        except Exception as e:
            hint = ''
            if isinstance(e, RecursionError):
                hint = (
                    '\nRecursionError here usually means process-wide state '
                    'corruption, not a defect in this element — e.g. a '
                    'partialmethod chain accumulated on MathTex/Text.__init__ '
                    'by repeated Mobject.set_default calls (docs/gotchas.md).'
                )
            logger.warning(
                'CreateMObject failed for "%s" (%s): %s%s\n%s',
                elem.name,
                type(elem.data).__name__ if elem.data else 'None',
                e,
                hint,
                traceback.format_exc(),
            )
            return None
```

- [ ] **Step 4: Убедиться, что тесты проходят**

Run: `python3.13 -m pytest tests/test_mobject_default_leak.py -v`
Expected: 5 passed (3 из Task 2 + 2 новых).

- [ ] **Step 5: Commit**

```bash
git add tests/test_mobject_default_leak.py animageo/animageo.py
git commit -m "fix(render): point RecursionError render failures at the process-wide root cause"
```

---

### Task 5: Документация (gotchas, CHANGELOG) + полный прогон

**Files:**
- Modify: `docs/gotchas.md` (раздел `## manim`, новая запись после заголовка раздела)
- Modify: `CHANGELOG.md` (новая секция `[Unreleased]` над `[1.4.3]`)

**Interfaces:**
- Consumes: итог Task 1–4 (поведение уже в коде).
- Produces: только документация; код не меняется.

- [ ] **Step 1: Добавить запись в `docs/gotchas.md`**

В раздел `## manim` (после строки `## manim`, перед первой существующей записью) добавить:

```markdown
### `Mobject.set_default` накапливает partialmethod-цепочку — нельзя звать в горячем пути

**Обнаружено:** 2026-07-03, разбор RecursionError в animageo-web (см. `docs/archive/TZ-mathtex-set-default-recursion-leak.md`)

`cls.set_default(**kwargs)` в manim выполняет
`cls.__init__ = partialmethod(cls.__init__, **kwargs)`. Чтение `cls.__init__`
с класса проходит через дескриптор `partialmethod.__get__` и возвращает
скомпилированную функцию `_method`, а не сам объект `partialmethod` — поэтому
встроенное «сплющивание» вложенных partialmethod НЕ срабатывает, и каждый
вызов добавляет новый слой обёртки. Вызов на каждый рендер (как раньше в
`setStyle`) растил глубину цепочки линейно; после ~1000 вызовов в одном
долгоживущем процессе (превью animageo-web, Celery-воркеры) любое
конструирование `MathTex`/`Tex`/`Text` падало с `RecursionError`. Симптомы
выглядели по-разному: молча выпадали точки и подписи (per-element recovery в
`_render_*`), падал `autoPlaceLabels` (bbox-измерение через Tex), ломались
value-подписи (`DecimalNumber` в manim 0.20 строит глифы через
`mob_class=MathTex`).

**Правила:**

1. Не вызывать `set_default` в коде, исполняемом на каждый рендер. Из
   `setStyle` он удалён; цвет подписей передаётся явно (`col_label` в
   `_build_render_ctx` → `create_label`).
2. Если глобальный дефолт всё же нужен (скрипты, примеры) — ставить один раз
   на процесс, либо делать вызов идемпотентным: сначала `cls.set_default()`
   (сброс к `_original__init__`), затем `cls.set_default(color=...)`.
3. `set_default()` без аргументов полностью восстанавливает оригинальный
   `__init__` — этим пользуются тестовые фикстуры
   (`tests/test_mobject_default_leak.py`).
4. У `Tex`, созданного с явным `color=`, верхний `get_fill_color()` может
   вернуть `None` — фактический цвет глифов проверять по
   `family_members_with_points()`.
```

- [ ] **Step 2: Добавить запись в `CHANGELOG.md`**

Над секцией `## [1.4.3] — 2026-06-30` вставить:

```markdown
## [Unreleased]

### Fixed

- **RecursionError after ~1000 renders in one process (labels and points
  silently vanishing).** `applyStyle` called `Text/MathTex/MarkupText
  .set_default(color=…)` on every invocation; manim's `set_default` wraps the
  current `__init__` in a new `functools.partialmethod` each time (nested
  partialmethods never flatten because the class attribute read returns the
  descriptor's compiled `_method` function), so the chain grew by one layer
  per render. Once it exceeded `sys.getrecursionlimit()`, every label
  construction raised `RecursionError`: per-element error recovery silently
  dropped points and labels, `autoPlaceLabels` crashed on Tex bbox
  measurement, and DecimalNumber-backed value labels failed too. The
  `set_default` calls are removed: the label render path always passes its
  colour explicitly (`col_label`), and `ShowText` now receives explicit
  colours too. `setStyle` no longer mutates any global manim class state,
  which also makes concurrent renders in threads safe from racing on
  `MathTex.__init__`.
- **Cyclic GGB macros no longer crash `loadGGB` with RecursionError.**
  `expand_macros_in_construction` recursed once per expansion pass with no
  bound, so a `geogebra_macro.xml` whose macro body calls itself (directly
  or mutually) blew the stack after ~1000 passes. Expansion now stops after
  32 passes with a warning; the unexpanded calls surface through the
  existing unsupported-command diagnostics.
- **RecursionError render failures now log a root-cause hint.** A
  `RecursionError` caught by the per-element recovery in `CreateMObject` is
  process-wide state corruption, not an element defect; the warning now says
  so instead of reading like a per-element failure.
```

- [ ] **Step 3: Полный прогон тестов**

Run: `python3.13 -m pytest tests/ -q`
Expected: все проходят (985+, точное число плавает), 0 failed. Это закрывает ТЗ §6.3: снапшотные и рендерные тесты подтверждают, что вывод не изменился.

- [ ] **Step 4: Ручная проверка критерия ТЗ §6.1–6.2 (репро-скрипт из ТЗ)**

Run:

```bash
python3.13 - <<'EOF'
import functools
from manim import MathTex
from animageo.animageo import AnimaGeoScene

def chain_len(cls):
    init = cls.__dict__.get('__init__'); n = 0
    while isinstance(init, functools.partialmethod):
        n += 1
        pm = getattr(init.func, '__partialmethod__', None)
        if pm is None: break
        init = pm
    return n

scene = AnimaGeoScene()
scene.applyStyle()
for i in range(2000):
    scene.setStyle(scene.style)
print("chain_len:", chain_len(MathTex))   # ожидается 0
MathTex("x")                               # не должен падать
print("OK: MathTex constructible after 2000 style applications")
EOF
```

Expected: `chain_len: 0` и `OK: MathTex constructible after 2000 style applications`.

- [ ] **Step 5: Commit**

```bash
git add docs/gotchas.md CHANGELOG.md
git commit -m "docs: gotcha + changelog entries for the RecursionError fixes"
```

---

## Соответствие критериям приёмки ТЗ (§6) и запросу «RecursionError в разных ситуациях»

| Критерий | Чем закрыт |
|---|---|
| §6.1 `chain_len` ограничена (≤1) | Достигнуто 0: `test_apply_style_does_not_grow_init_chain` (50 × applyStyle), `test_tex_constructible_...` (1200 × setStyle) |
| §6.2 2000+ рендеров без RecursionError | CI-прокси: 1200 × setStyle (> recursionlimit 1000) + живое `MathTex("1")`; вручную — репро-скрипт Task 5 Step 4 на 2000 итераций |
| §6.3 цвет подписей не меняется | `test_point_label_color_unchanged` (основной путь), `tests/test_show_text_colors.py` (ShowText), полный прогон снапшотных тестов |
| §6.4 тредобезопасность (желательно) | Закрыто конструктивно: `setStyle` больше не мутирует глобальное состояние классов manim — гонки за `MathTex.__init__` не существует; инвариант зафиксирован assert'ом `_chain_len == 0` |
| Доп.: «разные ситуации» RecursionError — разные симптомы одной причины | Раздел «Расследование» документирует все пути падения (подписи, label placement, value-подписи, оси); все закрываются Task 1–2 |
| Доп.: независимый источник — циклические макросы | Воспроизведён и закрыт Task 3 (`TestCyclicMacroGuard`) |
| Доп.: будущие RecursionError диагностируются, а не тонут в WARNING | Task 4 — подсказка о process-wide причине в per-element recovery |
