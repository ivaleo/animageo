# Перспективы развития

Анализ кодовой базы, паттернов использования в примерах и архитектуры выявил следующие направления улучшений --- от критичных до стратегических.

---

## 1. Надежность вычислительного ядра

### ~~Краш при пересечении концентрических окружностей~~ --- ГОТОВО

~~`intersect_cc` делит на `center_dist_squared`, который равен нулю для окружностей с одинаковым центром.~~ Исправлено: проверка `np.isclose(center_dist_squared, 0)` возвращает None.

### ~~Отсутствие обработки ошибок в `Construction.apply`~~ --- ГОТОВО

~~Конструкция остаётся в частично обновлённом состоянии.~~ Исправлено: try-catch с откатом выходных элементов в None.

### ~~Отсутствие детекции циклов~~ --- ГОТОВО

~~`sortCommands` мог зациклиться.~~ Исправлено: топологическая сортировка алгоритмом Кана с проверкой на циклы (ValueError при обнаружении).

---

## 2. Расширение парсера GeoGebra

### ~~Неподдерживаемые типы элементов~~ --- ЧАСТИЧНО ГОТОВО

Парсер обрабатывает `point`, `numeric`, `angle`. Добавлены (2026-04):

| Тип | Статус | Модуль |
|-----|--------|--------|
| `line` с `=` | ГОТОВО | `ggb_parser.py` через `<coords x y z>` |
| `conic` | ГОТОВО | `lib_conic.py` + `<matrix A0..A5>` |
| `function` | ГОТОВО | `lib_function.py` (sympy + lambdify) |
| `implicitpoly` | ГОТОВО | `lib_implicit.py` + marching squares |
| `boolean` | Низкий приоритет | — |
| `list` | Низкий приоритет | — |
| `image` | Низкий приоритет | — |

### Хрупкий механизм пропуска XML-элементов

Переменная `xelems_left_to_pass` --- счётчик, который легко рассинхронизировать. Замена на явный автомат состояний (state machine) с документированными переходами сделает парсер надёжнее.

### ~~Нереализованные команды~~ --- ЧАСТИЧНО ГОТОВО

Команды, встречающиеся в .ggb-файлах. Реализованы (2026-04):

- `Ellipse(F1, F2, a)`, `Ellipse(F1, F2, pt_on_curve)` → `ellipse_ppi/ppm/ppp`
- `Hyperbola(F1, F2, a)`, `Hyperbola(F1, F2, pt)` → `hyperbola_ppi/ppm/ppp`
- `Parabola(F, directrix)` → `parabola_pl/ps/pr`
- `Conic(p1..p5)` — коника через 5 точек → `conic_ppppp`
- `Center`, `Focus`, `Vertex`, `Axes`, `MajorAxis`, `MinorAxis`, `Directrix`
- `Eccentricity`, `LinearEccentricity`, `SemiMajorAxisLength`, `SemiMinorAxisLength`
- `Coefficients`, `Polar`, `Tangent`
- `Intersect` для всех пар: Conic ∩ {Line, Circle, Conic, Ray, Segment, Arc};
  Function ∩ {Line, Conic, Circle, Function}; ImplicitCurve ∩ {Line,
  Segment, Ray, Conic, Circle, Function, ImplicitCurve}
- Актуализация 2026-05: public-name aliases (`Circular*`, `Circumcircular*`,
  `Perpendicular*`, `Reflect`), inline GeoGebra expression lowering,
  `Point(Ray/Arc/Locus)`, sampled `Locus(Point, Point)`, `Incircle`,
  `IsogonalConjugation`, `Length`, `Perimeter`, `Circumference`,
  `Radius(Conic)`, `Area(Conic)`, Function ∩ {Segment, Ray},
  Arc ∩ {Circle, Arc, Conic}.
- Актуализация 2026-07: `Trilinear(A, B, C, x, y, z)` → `trilinear_pppiii`
  (точка по трилинейным координатам относительно треугольника).
- Актуализация 2026-07 (Tier A/B «лёгких» команд): `Slope`, `Direction`,
  `UnitVector`, `PerpendicularVector`, `UnitPerpendicularVector`, `Dot`,
  `Cross`, `AffineRatio`, `CrossRatio`, `Midpoint(Conic)`, `Conic(6 чисел)`,
  `Ray(Point,Vector)`, `Point(Point,Vector)`, `ClosestPoint(path,point)`,
  `Dilate(obj,factor[,center])`, `Polar(Line,Conic)`. См.
  `docs/archive/geogebra_command_audit.md` → «план «лёгких» команд».
- Актуализация 2026-07 (Tier C, семейство `Tangent`): `Tangent(Line, Conic)`
  → `tangent_lK/Kl` (касательные, параллельные прямой),
  `Tangent(Point/x, Function)` → `tangent_pF/iF/mF` (касательная через
  производную) и `Tangent(Circle, Circle)` → `tangent_cc` (общие касательные
  двух окружностей, до 4).

Остаются нереализованные:

- Точный/символьный `Locus` и `LocusEquation`; текущий `Locus` — sampled
  polyline.
- `RadicalAxis`, `Power` --- задачи по окружностям.
- Точная `Circumference(ellipse)` --- сейчас используется численная формула
  Рамануджана.
- `OsculatingCircle`, `Curvature`, `ConjugateDiameter`, `PathParameter` ---
  специализированные.

---

## 3. Рендеринг (`CreateMObject`)

### ~~Система z-index~~ --- ГОТОВО

~~Магические числа z-index.~~ Исправлено: именованные константы в `constants.py` (Z_FILL, Z_FILL_INNER, Z_FILL_LABEL, Z_ANGLE, Z_LINE, Z_STROKE, Z_POINT, Z_LABEL).

### Отсутствие обработки нерисуемых типов

Если элемент --- Measure, Boolean или AngleSize (без визуального представления), `CreateMObject` молча возвращает None. Стоит логировать это как debug, а не как ошибку.

### Дублирование паттерна "заливка + контур"

Шесть типов элементов (Polygon, Circle, Arc, CircleSector, Angle, Point) создают пару fill+stroke mobjects с почти одинаковой логикой. Вынесение в хелпер сократит ~80 строк.

---

## 4. Производительность

### Сортировка команд --- O(n^2)

`sortCommands` использует вложенные циклы. Для конструкций с 100+ командами это незаметно, но при масштабировании до 1000+ (веб-сервис) станет узким местом. Замена на алгоритм Кана (топологическая сортировка, O(n+m)) решит проблему.

### ~~Полный rebuild при каждом `putCode`~~ --- ГОТОВО

~~`putCode` вызывает `rebuild(full=True)` после каждого вызова.~~ Исправлено (2026-04): exec-движок использует `Construction.add_and_build`, который инкрементально пересчитывает только новый узел (`rebuild(full=False)`).

---

## 5. Удобство API

На основе анализа 28 примеров:

### ~~Пакетные операции со стилями~~ --- ГОТОВО

~~Сейчас: цикл по элементам вручную.~~ Исправлено: `setElementStyle(names, **props)` и `setVisible(names, visible)`.

### ~~Гибкий импорт GGB-стилей~~ --- ГОТОВО

~~Монолитный импорт: либо всё из GGB, либо ручные overrides через `setElementStyle`.~~ Исправлено: `ImportPolicy` (см. `animageo/style/import_policy.py` и [docs/import_policies.md](import_policies.md)). Поддерживает literal overrides, callables, DSL (`const:`/`scale:`/`quantize:`/`remap:`), конфигурацию из JSON (`import.policy`) и `reloadPolicy()` без повторного парсинга XML. Per-type/per-name стилизация живёт в `overlay`. Формулы масштабирования вынесены из парсера в `style/scaling.py` (именованные функции вместо магических чисел). Элементы хранят сырые GGB-значения в `elem.ggb_raw`.

### ~~StyleConfig: три слоя (defaults / overlay / ggb-policy)~~ --- ГОТОВО

~~`ImportPolicy` смешивал две разные задачи: GGB-трансформации и per-type/per-name стилизация. Второе не применялось к DSL-элементам (пустой `ggb_raw`), из-за чего guide-рендерер вручную дублировал policy для DSL. Плюс часть scene-level размеров проходила двойное масштабирование и коллапсировала в субпиксель на DSL.~~ Исправлено:

- `animageo/style/config.py` — новый `StyleConfig` с тремя слоями: `DefaultsProfile` (per-type baseline в пикселях), `StyleOverlay` (`per_type`/`per_name` + автоматика), и `ImportPolicy` (raw-GGB трансформации).
- `animageo/style/builtin.json` — package-shipped дефолты; всегда загружается, user JSON сливается через `deep_merge`.
- `animageo/style/resolver.py` — `resolve(scene, elem, key)` обходит цепочку `elem.style → per_name → per_type → ggb_style → defaults`. Overlay читается лениво из `StyleConfig`, без записи в `elem.style`.
- Phase 4 unit fix: `ang_rdefault`/`ang_rshift`/`ang_right`/`dot_size` теперь в пикселях — `×0.02` убрано из `GeoStyle.load_from_json`.
- Phase 3 (частично): `CreateMObject` преамбула (stroke/fill/opacity/label_color) и Point + Angle блоки читают через resolver. `compute_effective_arc_size_px` принимает `base_px=` для поддержки builtin-defaults на DSL-углах.
- `overlay.angle_radius` / `overlay.label_placement` живут только в `overlay.*` в style JSON.
- guide-рендерер больше не replay-ит `import.policy` для DSL; локальная подстройка `strich_width` удалена после перехода tick/arrow/font на resolver `*_px`.
- +76 тестов; 923 зелёных на текущей ветке.

**Закрыто перед 1.1.1:** unit-reform для `strich_*`, `arrow_*`, `label_r_offset`, `line_width`, `font_size`: старые ключи отклоняются, runtime читает canonical `*_px` через resolver. Полная миграция per-type блоков `CreateMObject` на resolver продолжается точечно для не-визуальных путей.

### Именованные методы для типичных действий

```python
# Вместо
self.element('s').style['stroke_dash'] = 0.65
self.element('s').style['stroke_opacity'] = 0.5

# Предложение
self.element('s').setDashed(0.65).setOpacity(0.5)
```

### ~~Контекст анимации~~ --- ГОТОВО

~~Ручной addUpdater/clearUpdater.~~ Исправлено: контекстный менеджер `self.animating(tracker)`.

### ~~Динамическая расстановка подписей~~ --- ГОТОВО

~~Статический `autoPlaceLabels()` корректен только для снимка; при анимации подписи углов уезжают с биссектрисы, подписи точек могут наезжать друг на друга, а переcчёт решателя на каждом кадре даёт прыжки.~~ Исправлено (2026-04):

- `label_placement.py` разделён на pure `compute_label_layout` и impure `apply_label_layout`; извлечена `compute_angle_label_center` (биссектриса по живым `ang.side1/side2/vertex`).
- `play_keyframes` при `keyframe_snapshots=true` делает pre-pass: считает раскладку на каждом keyframe и интерполирует offset’ы между ними. Углы дополнительно трекаются per-frame.
- `autoPlaceLabels(dynamic=True)` ставит `LabelTracker` — для `addUpdater`-анимаций решатель работает на каждом кадре, статические подписи сглаживаются через EMA (`apply_ema_step`), якоря залипают Schmitt-триггером (`anchor_hysteresis_step`).
- Опциональная MC-канонизация (`canonicalize_anchor=true`) убирает дискретные скачки якоря.
- Конфиг — `overlay.label_placement.*` (9 новых ключей), API — `autoPlaceLabels(dynamic=False)` + `clearLabelTracker()`.

**Что ещё можно:** soft-repulsion между подписями (устранение нахлёстов между keyframe), бенчмарк на больших сценах, миграция snapshot-тестов для default-on canonicalize.

### ~~Multi-arc, раздельные зазоры, авто-подбор радиуса дуги~~ --- ГОТОВО

Исправлено (2026-04-19):

- **Multi-arc aware раскладка**: при `elem.style['tick_count'] > 1` подпись угла отодвигается за внешнюю дужку (формула `arc_size_px + (lines − 1) · ang_rshift` в одной функции `_angle_effective_arc_r_px`, та же что в рендере).
- **Раздельные зазоры** `angle_gap_arc_px` (дуга → подпись) и `angle_gap_sides_px` (стороны → bbox подписи). `angle_gap_px` удалён и больше не fallback.
- **`overlay.angle_radius`** — новая секция конфига с авто-скалированием `base · (pivot_rad / angle) ** exp` и клэмпами (`min_px`, `max_arm_fraction`). Общая функция `compute_effective_arc_size_px` используется и рендером (`CreateMObject`), и раскладкой (`_collect_labels` + `compute_label_layout`) — подпись автоматически следует за масштабированной дужкой. Default `enabled=false` сохраняет byte-for-byte GGB-импорт. Per-element opt-out: `elem.style['auto_radius'] = False`.
- Тестовое покрытие: +13 тестов (`compute_effective_arc_size_px` в 8 сценариях, multi-arc effective radius, split-gap independence).

---

## 6. Подготовка к веб-сервису

### ~~Компактный контекст для AI-генерации стилей~~ --- ГОТОВО

Перед 1.2.0 добавлен минимальный JSON-summary конструкции для передачи в AI
без исходного `.ggb`: типы, имена, базовые геометрические связи, стили GGB,
пересечения/наложения и bbox. Экспорт доступен как
`scene.exportStylePromptSummary(filepath=None, **kwargs)` и как низкоуровневые
функции `animageo.exporters.construction_summary`.

Связанные материалы:

- [construction_summary.md](construction_summary.md) — формат
  `animageo-construction-summary/v1`;
- [ai_style_generation_context.md](ai_style_generation_context.md) — полный
  prompt-контекст для AI, включая контракт `style` / `python_dsl` / `notes`;
- [ai_style_json_schema.json](ai_style_json_schema.json) — JSON Schema для
  проверки style JSON.

### AI-создание и редактирование конструкций --- ПРОРАБОТКА

Следующий этап AI-пайплайна должен работать не с внутренним graph JSON, а с
`scene.putCode(...)` / `scene.loadCode(...)` compatible Python DSL. Это
позволяет создавать новые конструкции, а также применять patch DSL после
`loadGGB(...)` или существующего DSL-source.

Ключевые решения:

- режимы: `create`, `patch`, `replace`;
- GGB-edit по умолчанию является patch-edit: добавление, visibility/style,
  новые зависимости и осознанное переопределение имен;
- `delete`/`rename` пока не являются безопасными публичными AI-операциями;
- construction summary остается read-only контекстом, а не форматом
  восстановления всей конструкции;
- для веб-сервиса нужны response schema, AST/DSL validator, isolated execution
  и structured diagnostics.

Связанный план: [ai_construction_generation_plan.md](ai_construction_generation_plan.md).
Первый экспериментальный контур: [ai_construction_generation_context.md](ai_construction_generation_context.md)
и [ai_construction_lab/index.html](ai_construction_lab/index.html).

### Программный API без manim CLI

Сейчас `__main__.py` генерирует временный Python-файл и вызывает `os.system('manim temp.py')`. Для интеграции в веб-сервис нужен программный интерфейс:

```python
from animageo import render

result = render(
    ggb_path='input.ggb',
    style='default.json',
    output_format='svg',       # или 'png', 'mp4', 'tikz'
    size=(800, 600),
)
```

> **Готово:** экспорт в TikZ реализован — `scene.exportTikZ(...)` /
> `python -m animageo file.ggb -o out.tex [--standalone]`. Семантический
> нативный TikZ (примитивы `\draw circle`/`ellipse`/`(a)--(b)`/`arc`, LaTeX
> `\node`-метки, `\draw plot coordinates` для сэмплируемых кривых). См.
> `docs/tikz_export.md` и пакет `animageo/exporters/tikz/`.

### Изоляция от файловой системы

`ggb_parser` распаковывает .ggb во временную директорию --- это уже исправлено (`tempfile.mkdtemp`). Но для веб-сервиса нужна поддержка работы с байтовыми потоками (bytes/BytesIO) без обязательного сохранения на диск.

### Кэширование конструкций

Парсинг .ggb и построение конструкции можно кэшировать. При повторных запросах с тем же файлом не нужно заново парсить XML.

---

## 7. Качество кода

### ~~`_stubs.py`~~ --- УСТАРЕЛ

Старый файл `_stubs.py` оставлен для обратной совместимости, но больше не нужен. Современные `.pyi` стабы для DSL:
- `animageo/parsers/dsl/namespace.pyi` — 74 фабрики
- `animageo/parsers/dsl/proxy.pyi` — типы элементов (Point, Line, Circle, ...)
- `animageo/style/proxy.pyi` — StyleProxy
- `animageo/dsl.pyi` — super-module re-exports для `from animageo.dsl import *`

Регенерация списка фабрик: `python3 -m animageo.parsers.dsl._regen_stubs`.

### Покрытие тестами

846 тестов покрывают ядро. Не покрыто:
- Manim-рендеринг (CreateMObject) --- требует визуальных snapshot-тестов
- SVG-экспорт (svg_parser) --- требует сравнения выходных файлов
- Анимации (Show/Hide/Shade) --- требует manim test framework
- CLI (__main__.py)

### Логирование

Логирование внедрено, но `debug` параметры в `loadGGB`, `rebuild`, `putCode` по-прежнему контролируют вывод через `if debug: logger.debug(...)`. Стоит убрать параметр `debug` и полагаться только на уровень логгера.

---

## Приоритеты

| # | Направление | Влияние | Сложность | Статус |
|---|-------------|---------|-----------|--------|
| 1 | ~~Фикс `intersect_cc`~~ | Критично | Низкая | ГОТОВО |
| 2 | ~~Обработка ошибок в `Construction.apply`~~ | Высокое | Низкая | ГОТОВО |
| 3 | ~~Расширение парсера GeoGebra (line, conic, function, implicitpoly)~~ | Высокое | Средняя | ГОТОВО |
| 4 | ~~Пакетные операции со стилями~~ | Среднее | Низкая | ГОТОВО |
| 5 | ~~Формализация z-index тиров~~ | Среднее | Низкая | ГОТОВО |
| 6 | ~~Топологическая сортировка команд~~ | Среднее | Средняя | ГОТОВО |
| 6a | ~~Гибкий импорт GGB-стилей (ImportPolicy)~~ | Высокое | Средняя | ГОТОВО |
| 7 | Программный API для веб-сервиса | Высокое | Средняя | |
| 8 | ~~Команды коник (Center/Focus/Vertex/Tangent/Polar/Ellipse/Hyperbola/Parabola)~~ | Среднее | Средняя | ГОТОВО |
| 8a | Оставшиеся GGB-команды (sampled Locus, Incircle, aliases, extra Intersect закрыты; RadicalAxis/Power/Curvature остаются) | Низкое | Высокая | ЧАСТИЧНО |
| 10 | ~~DSL-сахар `f(x) = expr` + string-args~~ | Среднее | Низкая | ГОТОВО |
| 11 | ~~Python-DSL с циклами/условиями/kwargs (exec-движок, 87 автообнаруженных фабрик, `.pyi` стабы, sandbox)~~ | Высокое | Высокая | ГОТОВО |
| 12 | ~~Ревизия имён полей (убраны `.a`, `.c`, `.n`, `.r`, `.M`, `.b`, `.x`, `.alpha` и др.)~~ | Высокое | Высокая | ГОТОВО |
| 13 | ~~Компактный summary конструкции + AI style-generation context/schema~~ | Высокое | Средняя | ГОТОВО |
| 14 | AI-создание и patch-редактирование конструкций через DSL | Высокое | Высокая | ПРОРАБОТКА |
| 9 | Snapshot-тесты для рендеринга | Среднее | Высокая | |
