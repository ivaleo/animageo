# Известные особенности и подводные камни

Файл фиксирует неочевидные особенности manim, Python и внутренней архитектуры animageo, обнаруженные при разработке и тестировании. Учитывать при развитии функционала.

---

## manim

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

### `tex_template` работает только в конструкторе — `.set(tex_template=…)` бесполезен

**Обнаружено:** 2026-07-25, разбор инцидента animageo-web (исчерпание пула БД)

`Tex.__init__` компилирует LaTeX **немедленно**: если `tex_template` не передан
аргументом, берётся `config["tex_template"]`. Присвоение после конструктора —
`Tex(s).set(font_size=…, tex_template=RusTex)` — лишь кладёт атрибут на уже
скомпилированный объект и на рендер **не влияет**. Ровно так подписи и строились
в `create_label`: шаблон выглядел переданным, а компиляция шла под стоковым
не-кириллическим шаблоном manim, и любая кириллическая подпись роняла весь
элемент (`CreateMObject failed` → пропадали и маркер, и подпись).

**Правила:**

1. `tex_template` — только аргумент конструктора.
2. Кириллице-совместимый шаблон ставится глобальным дефолтом один раз при
   инициализации сцены: `ui.install_cyrillic_tex_template()` (вызывается из
   `AnimaGeoScene.__init__`). Это НЕ `Mobject.set_default` — обычное
   идемпотентное присваивание `config.tex_template`, цепочка partialmethod не
   накапливается. Чужой (не стоковый) шаблон функция не перетирает.
3. Падение компиляции подписи не должно уносить элемент: `ui._compile_label_tex`
   деградирует LaTeX → экранированный plain-text → `None` (элемент рисуется без
   подписи), а `_measure_label_bbox` в этом случае оценивает габариты.

### Кириллица в математическом режиме компилируется в пустоту

**Обнаружено:** 2026-07-25, там же

Это хуже ошибки: `$Б$` под `T2A` **успешно** компилируется и не рисует ничего —
в математическом алфавите нет кириллических глифов. Симптомы: подпись `$Б_1$`
показывала одинокую «1», а из текста `Отрезок $БВ$ равен` молча пропадал кусок.
Воспроизводится и в manim (latex→dvisvgm), и в TikZ-экспорте (pdflatex).

**Правило:** кириллический прогон внутри `$…$` переводить в текстовый режим —
`geo.lib_elements.textify_cyrillic` (`$Б$` → `$\text{Б}$`, под индексом ещё и в
скобках: `$A_{\text{Б}}$`, иначе `_\text` съест только команду). Применяется в
`correctedLabel`, `_render_text` и TikZ (`TikzContext.label_text`, `emit_text`).
Кириллицу, уже набранную в текстовом режиме, не трогаем — она рендерится и так.
JSXGraph-экспорт не затронут: подписи там идут через MathJax, у которого
кириллица в математике есть.

### Рендер внешней сцены AnimaGeo через Manim

**Обнаружено:** 2026-05-03, при проверке `examples/21 -  Задача Феди про линзы/anima21.py`

В рабочем окружении проекта команда `python3 -m manim ...` может попасть в
Python без установленного `manim`. Надёжная команда для локального рендера
примеров:

```bash
PYTHONPATH=/path/to/animageo manim anima21.py Scene21 -ql --format=png --media_dir /tmp/animageo_scene21_render
```

Если нужно запускать pytest/служебные проверки в том же окружении Manim,
используйте Python 3.13 из Homebrew:

```bash
/opt/homebrew/opt/python@3.13/bin/python3.13 -m pytest ...
```

### Updater на анимируемом объекте не получает промежуточных значений

**Обнаружено:** 2026-04-14, при отладке `play_keyframes`

Если `add_updater(func)` вызван на том же `ValueTracker`, который анимируется через `.animate.set_value()`, то внутри `func` вызов `mob.get_value()` (где `mob` — параметр, переданный manim'ом) возвращает только начальное и конечное значения, но никогда промежуточные. Причина — manim при анимации создаёт копии start/end состояний объекта и вызывает updater на этих копиях, а не на интерполированном оригинале.

**Рабочие подходы:**

1. **Sentinel-объект** (используется в `play_keyframes`): updater живёт на отдельном невидимом `Mobject`, а `ValueTracker` читается через замыкание:
   ```python
   progress = ValueTracker(0)
   sentinel = Mobject()
   def on_frame(mob):
       t = progress.get_value()  # замыкание — читает оригинал
       ...
   sentinel.add_updater(on_frame)
   self.add(progress, sentinel)
   self.play(progress.animate(...).set_value(1), ...)
   ```

2. **Замыкание вместо параметра** (используется в `addUpdater`): updater на трекере, но внутри обращается к переменной из замыкания, а не к параметру `mob`:
   ```python
   tracker.add_updater(lambda v, self=self: self.updateVar(tracker))
   #                                                       ^^^^^^^ замыкание, не v
   ```

**Не работает:**
```python
tracker.add_updater(lambda v: do_something(v.get_value()))
#                              ^^^^^^^^^^^ v — копия, не оригинал
```

### Polygon не поддерживает become()

В manim `become()` не корректно работает для `Polygon` (мерцание, неправильная анимация). Поэтому в `updateGeoElements` полигоны обрабатываются через remove + add, а не через `become()`. Это известная особенность manim, а не баг animageo.

Такой remove + add не должен менять порядок слоев: фактический Manim
`z_index` дополнительно получает микросдвиг по порядку элемента в конструкции.
Это сохраняет порядок внутри одного слоя (`Z_STROKE`, `Z_POINT` и т. п.) в
статике и во время MP4-анимации.

---

## Расстановка подписей

### `dynamic_angles=true` сам по себе ничего не делает

**Обнаружено:** 2026-04-17, при проектировании динамической раскладки

Флаг `overlay.label_placement.dynamic_angles=true` помечает углы для биссектрисного трекинга, но кто-то должен фактически вызывать `compute_angle_label_center` каждый кадр. Два легальных способа это включить:

1. **`play_keyframes` с `keyframe_snapshots=true`** — on_frame вызывает пересчёт автоматически.
2. **`scene.autoPlaceLabels(dynamic=True)`** — устанавливает `LabelTracker`, и `updateVar` (который дёргается на каждое изменение трекера внутри `addUpdater`) перезаписывает оффсеты.

Если включить только `dynamic_angles=true`, не дёрнув ни того, ни другого — углы статические, как раньше. Это сделано намеренно, чтобы опция была cheap to enable в конфиге, а стоимость per-frame работы была явным выбором точки интеграции.

### MC-канонизация по умолчанию выключена

**Обнаружено:** 2026-04-17, при проектировании

`canonicalize_anchor=true` переписывает `label_anchor='MC'` с компенсирующим оффсетом. Это исключает прыжки якоря при интерполяции между keyframe, но ломает snapshot-тесты в `test_loadggb_snapshot.py` — они зафиксировали `label_anchor='BC'/'ML'/...` из старого решателя. Поэтому default — false; включать только когда нужна плавность динамики.

### Tex bbox кэш — модульный, не per-scene

`_bbox_cache` в `label_placement.py` — process-wide dict, keyed по `(label_text, font_size)`. При смене font_size в GeoStyle между двумя сценами в одном процессе кэш переиспользуется корректно (ключ включает font_size). Но если вы меняете TeX-шаблон (`RusTex`) в памяти руками — вызовите `clear_bbox_cache()`. `play_keyframes` делает это автоматически в начале snapshot pass.

### `overlay.angle_radius` выключен по умолчанию

**Обнаружено:** 2026-04-19, при внедрении авто-подбора радиуса дуг

`compute_effective_arc_size_px` (shared между рендером и раскладкой подписей) применяет масштабирование `(pivot_rad / angle) ** exp` + clamps только когда `overlay.angle_radius.enabled=true`. Default `false` — байт-в-байт импорт из GGB сохраняется, snapshot-тесты не ломаются.

Включать осознанно: при `enabled=true` визуальный размер дуг всех углов в сцене поменяется (узкие станут больше, широкие — меньше). Для точечного отключения используйте per-element escape: `elem.style['auto_radius'] = False`.

### `angle_gap_px` удалён

**Обновлено:** 2026-05-18, при удалении старых alias/fallback

Ключ `overlay.label_placement.angle_gap_px` больше не читается. Используйте
два явных ключа: `angle_gap_arc_px` для зазора дуга→подпись и
`angle_gap_sides_px` для зазора стороны→bbox подписи.

---

## GeoGebra import

### `Point(Conic)` должен сохранять параметр из XML-координат

**Обнаружено:** 2026-05-03, на `examples/21 -  Задача Феди про линзы/scene21.ggb`

GeoGebra может создавать точку на конике командой `Point(e)`, где `e` —
`Conic` (например, гипербола). Если импортёр не поддерживает `Point(Conic)`,
такая точка остаётся `data=None`, а все downstream-команды (`Line`, `Intersect`,
`Segment`, `Distance`, `CircumcircleArc`, `Angle`) ломаются каскадом.

Фикс: команда `point_K` строит точку на circle/ellipse/hyperbola/parabola в
канонической параметризации, а GGB-парсер вычисляет `elem.tparam` из
координат `<element type="point">`. Для гиперболы параметр хранится как
`(branch, t)`, чтобы сохранять выбранную GeoGebra ветвь.

### `CircumcircleArc(A, M, B)` выбирает дугу через среднюю точку

**Обнаружено:** 2026-05-03, на `examples/21 -  Задача Феди про линзы/scene21.ggb`

Правило GeoGebra: `CircumcircleArc(A, M, B)` строит дугу окружности с концами
`A` и `B`, которая проходит через `M`. Поэтому относительно хорды `AB`
выбранная дуга должна оказаться с той же стороны от прямой `AB`, что и `M`
(если `M` не лежит на самой прямой).

Типовая ошибка реализации: `Arc` хранит диапазон как развернутый интервал
`[angle_start, angle_end]`, где `angle_end` может быть больше `2π`, а
проверяемая точка вычисляется через `np.angle(...)` в диапазоне `[-π, π]`.
Сравнивать эти значения напрямую нельзя: дуги, пересекающие нулевой угол,
начинают ошибочно считаться не содержащими свою среднюю точку. Перед
сравнением угол точки должен быть приведен в тот же развернутый интервал.

### Unicode-имена в GGB-командах должны оставаться прямыми ссылками

**Обнаружено:** 2026-05-03, на `examples/17 - Два луча в угле/scene17.ggb`

GeoGebra нормально использует имена вроде `α` и `β` как labels. Если проверять
"простое имя" ASCII-регуляркой, команда `Intersect(β, k, 1)` превращается в
выражение через phantom-переменную (`_1 = β`), а при неудачном разрешении
downstream-команды получают `None`.

Правило: после нормализации имени `str.isidentifier()` является системной
проверкой простого Python/DSL-идентификатора. Unicode labels должны проходить
как обычные ссылки на существующие элементы.

В той же сцене GeoGebra использует `Intersect(β, k, 1)` и `Intersect(β, l, 1)`,
где `β` — дуга, а `k/l` — лучи. Поэтому AnimaGeo поддерживает не только
`Arc ∩ Line`, но и индексные пересечения `Arc ∩ Ray` / `Arc ∩ Segment`.

### `loadCode` может переопределять GGB-элементы и обязан пересобрать граф

**Обнаружено:** 2026-05-03, на `examples/17 - Два луча в угле/anima17.py`

`anima17.py` загружает `.ggb`, затем выполняет `scene17.py`. В этом DSL-файле
имя `E` используется повторно:

```python
E = Rotate(D + Vector(r2, 0), ang2 * deg, D)
```

В исходном `.ggb` `E` было точкой `Intersect(β, k, 1)`, от которой зависел
`m = Segment(B, E)`. После переопределения имени downstream-команды должны
пересчитаться уже от нового `E`. Поэтому после `loadCode()` / `putCode()`
нужен финальный `geo.rebuild(full=True)` перед `updateAllGeometry()`;
иначе в рендер может попасть stale-геометрия старого `m`.

## Python

### Циклический импорт lib_elements ↔ lib_vars

`lib_elements.py` импортирует из `lib_vars.py` (`from .lib_vars import *`), а `lib_vars.py` импортирует из `lib_elements.py` (`from .lib_elements import Angle`). Этот циклический импорт разрешается корректно **только если `lib_vars` импортируется первым** (как это делает `construction.py`).

Если в тестах или внешнем коде первым импортировать `lib_elements`, возникает `ImportError: cannot import name 'Angle' from partially initialized module`.

**Правило:** всегда импортировать `construction` (или `lib_vars`) до `lib_elements`:
```python
from animageo.geo.construction import Construction  # первым
from animageo.geo.lib_elements import Point, Line   # потом
```

### ImportPolicy: DSL-строки парсятся в `__post_init__`, а не в resolve()

Раньше `parse_directive` вызывался только внутри `ImportPolicy.from_dict()`. Это приводило к тому, что `ImportPolicy(stroke_width_px='quantize:[1,3,6]')` хранил литеральную строку, и в `resolve_overrides_only` она уходила как значение `elem.style['stroke_width_px']` — дальше манимовская конвертация толщины ломалась (строка вместо числа → линии не отрисовывались).

Фикс (с апреля 2026): `__post_init__` в `ImportPolicy` прогоняет все поля через `parse_directive`, так что DSL-строки работают одинаково при загрузке из JSON и при прямой передаче в конструктор.

**Следствие:** если кто-то хочет передать литеральную строку, совпадающую с DSL-префиксом (маловероятно), её нужно оборачивать в callable: `ImportPolicy(label_color=lambda *_: 'scale:1.5_as_literal')`.

### `elem.ggb_raw` отсутствует у элементов, созданных через Python DSL

Поле `ggb_raw` заполняется только парсером `.ggb`. Для элементов, добавленных через `loadCode`/`putCode`, оно остаётся пустым dict. Поэтому `ImportPolicy` считается GGB-only слоем: raw-derived правила работают на импортированных элементах, а для DSL нет исходного GGB значения.

**Фикс (текущий рефакторинг):** типовые и именные правила вынесены в `StyleOverlay`. `scene.style_config.overlay.apply(scene)` вызывается автоматически в `addAllGeometry` и работает одинаково для GGB и DSL через `type(elem.data)`. Для стилизации поверх импорта (per_type/per_name + autoPlaceLabels) — задавайте `overlay` в JSON. `ImportPolicy` оставлен для raw-GGB трансформаций (`scale:`/`quantize:`/`remap:`).

### Пре-Phase-4: angle/dot размеры в JSON умножались на 0.02 и коллапсировали

До перехода на canonical `*_px` поля часть scene-level размеров проходила через `json_size_to_internal` (× 0.02), а рендерер затем **ещё раз** делил на `ptUnit`. На обычном холсте это превращало нормальный радиус дуги в субпиксельный размер, и дуга могла схлопнуться в невидимую точку на DSL-сценах.

GGB-сцены не страдали, потому что парсер писал `arc_size_px` прямо в `elem.style` (минуя scene-level `ang_rdefault`). Поэтому баг выявился только на Python-DSL.

**Фикс:** canonical schema хранит размеры как semantic `presets` (`angle_radius.*`, `point_size.*`, `tick.*`, `arrow.*`) и применяет их через per-type `defaults`. Все `*_px` значения интерпретируются как пиксели и конвертируются в render-time по целевому Manim-параметру: координатные размеры делятся на `ptUnit`, а `stroke_width`/`font_size` значения идут через Manim-шкалу `* 100 / ptUnit`. См. `tests/test_angle_units_regression.py`.

### `tick_width_px` — это stroke width, а не координатная длина

`tick_length_px`, `tick_shift_px` и `tick_radius_px` участвуют в геометрии tick-метки, поэтому рендерятся как координатные размеры: `px / ptUnit`.

`tick_width_px` используется иначе: segment/vector tick передают его в Manim `Line(..., stroke_width=...)` или `VMobject.set_stroke(width=...)`. Это тот же unit system, что и `stroke_width_px`, поэтому правильная конвертация — `stroke_width_to_manim(tick_width_px, ptUnit)`, то есть `tick_width_px * 100 / ptUnit`. Деление только на `ptUnit` делает tick stroke в 100 раз тоньше при SVG/export render. См. `tests/test_style_config_integration.py::TestPixelInvariantDecorations`.

### `python -m animageo` не должен тянуть Manim до проверки аргументов

Обычный `import animageo` по-прежнему экспортирует Manim-backed API. Но CLI path (`python -m animageo file.ggb`) держится лёгким до проверки входных файлов, чтобы ошибки вроде missing file возвращались сразу и не инициализировали тяжёлый runtime.

---

## Python DSL

### `putCode`/`loadCode` — только exec-движок (short_parser удалён)

**Обнаружено:** 2026-04 (миграция)

До серии ревизий 2026-04 DSL работал через AST-walker (`short_parser.py`),
который молча игнорировал циклы, условия, `def`, kwargs. После
миграции `short_parser.py` удалён — используется только exec-движок
(`parsers/dsl/`). `engine=` kwarg у `putCode`/`loadCode` тоже убран.

Если внешний код передавал `engine='legacy'` — он теперь даёт
`TypeError: got unexpected keyword argument 'engine'`. Убирайте kwarg.

### Forward-ref для lowercase имён

**Обнаружено:** 2026-04, при миграции scene{N}.py в exec-движок

Паттерн в anima.py:
```python
self.loadGGB(...)                  # populates A, B, R, Q …
self.loadCode('scene.py')          # scene.py references x
self.addVar('x', 115)              # x gets its value AFTER loadCode
```

Exec-движок поддерживает такой forward-reference для **lowercase** имён: `FactoryDict.__missing__` авто-создаёт Var-плейсхолдер с `data=None`, Command запоминает имя, резолвится при `rebuild`. Для uppercase — `Rotat` (опечатка от `Rotate`) поднимает ошибку в runtime, это специально для ловли опечаток.

### Backward-compat алиасы полей удалены

**Обнаружено:** 2026-04, финальная ревизия именований

Короткие/абстрактные имена (`.a`, `.c`, `.n`, `.r`, `.v`, `.M`, `.b`, `.x`, `.dim`, `.angle`, `.original`, `.points`, `.end_points`, `.start_point`) полностью заменены на человечные (`.coords`, `.center/.offset`, `.normal`, `.radius`, `.direction`, `.matrix`, `.value`, `.dimension`, `.tparam`, `.size`, `.source`, `.vertices`, `.endpoints`, `.start`). Алиасы сняты — старый код получает `AttributeError`.

Полный список — [docs/field_names.md](field_names.md). JSON wire-format keyframe-анимации использует `tparam_point` и ключ `tparam`.
