# Аудит `docs/guide` относительно текущей кодовой базы AnimaGeo

Дата аудита: 2026-05-04.
Объект аудита: текущая рабочая версия репозитория, включая уже существующие незакоммиченные изменения.

## Короткий вывод

`docs/guide` уже описывает большую часть пользовательского пути: установку,
первую сцену, Python DSL, загрузку `.ggb`, новую JSON-схему стилей,
автораскладку подписей, кривые, keyframe/updater-анимации и SVG/MP4 экспорт.
Интерактивные примеры в гайде в текущей среде рендерятся: проверены 26
блоков `.ex.interactive`, ошибок рендера нет.

Главная проблема не в отсутствии основного материала, а в дрейфе reference и
нескольких статических рецептов относительно текущей реализации. В коде уже
закреплена canonical-схема `*_px` и resolver-цепочка
`elem.style -> overlay -> ggb_style -> defaults`, но в §11 и отдельных местах
гайда ещё встречаются старые runtime-ключи (`size`, `stroke_dash`,
`stroke_cap`, `right_mark`, `lines`, `lines_type`). Такие записи либо ничего
не делают, либо вводят пользователя в неверную модель.

Вторая крупная зона: гайд почти не описывает AI/style-summary pipeline,
CLI `animageo`, ограничения DSL sandbox, подробную диагностику unsupported
GeoGebra-команд и эксплуатационные нюансы окружения. Эти темы есть в коде и
в соседних `docs/*.md`, но не доведены до интерактивного гайда.

## Что проверялось

- Структура и тексты `docs/guide/*.html`, `docs/guide/README.md`.
- Публичный API в `animageo/animageo.py`, `animageo/__main__.py`.
- DSL-движок: `animageo/parsers/dsl/*`, `animageo/dsl.py`,
  `animageo/geo/lib_commands.py`.
- Стилевой слой: `animageo/style/config.py`, `schema.py`, `resolver.py`,
  `import_policy.py`, `builtin.json`.
- Подписи, keyframes, кривые и summary exporter.
- Тесты и соседняя документация: `docs/api.md`, `docs/python_dsl.md`,
  `docs/gotchas.md`, `docs/construction_summary.md`,
  `docs/archive/geogebra_command_audit.md`, `tests/*`.

Проверки:

- `docs/guide`: 26 интерактивных примеров отрендерены через
  `docs.guide.server.runner.render_example(...)`, все успешно.
- Точечные тесты:
  `tests/test_guide_overlay.py`, `tests/test_import_policy.py`,
  `tests/test_label_modes.py`, `tests/test_construction_summary_export.py`
  прошли на `/opt/homebrew/opt/python@3.13/bin/python3.13`: `67 passed`.
- На обычном `python3` в этой машине тесты не собираются из-за отсутствия
  `manim` в Python 3.14. Это не ошибка библиотеки, но эксплуатационный нюанс,
  который в гайде стоит сделать заметнее.

## Что в гайде описано хорошо

### §1-§2: вводный путь и первый запуск

Покрыто:

- Что такое AnimaGeo: `.ggb`/Python DSL -> `Construction` -> Manim mobjects
  -> SVG/MP4.
- Отличие геометрии в math-units от визуальных размеров в пикселях.
- Минимальный `AnimaGeoScene.construct`.
- `applyStyle`, `putCode`, `addAllGeometry`, `autoPlaceLabels`, `exportSVG`.
- Локальный render-сервер гайда и предупреждение, что `/render` исполняет
  Python-код.

Что стоит усилить:

- В §2 есть проверка `python3.13 -c ...`, но не объяснено, что на машине может
  быть несколько Python. В этом репозитории `python3` указывает на Python 3.14
  без `manim`, а рабочий путь для тестов/рендера - Python 3.13 Homebrew.
- Не описан пакетный CLI `animageo file.ggb -o out.svg -px ... -s ...`,
  хотя он есть в `animageo/__main__.py` и README.

### §3: Python DSL

Покрыто:

- Основные примитивы: `Point`, `Line`, `Segment`, `Ray`, `Vector`, `Circle`,
  `Polygon`, `Angle`.
- Tuple-unpack (`p, a, b, c = Polygon(...)`, `L1, L2 = Intersect(...)`).
- Явные имена через `name=`.
- Циклы, функции, f-строки, field access через proxy.
- Стиль внутри DSL через `A.style.foo = ...` и batch-helper `style(...)`.
- Dispatch convention через type shortcuts.
- Стабы `<ggb>_stubs.pyi` после `loadGGB`.

Расхождение с реализацией:

- Текст "Полный Python внутри DSL" слишком широкий. Реализация в
  `parsers/dsl/transform.py` запрещает или удаляет часть Python:
  `import`/`from import` удаляются, `global`, `nonlocal`, `+=`,
  annotated assignment с value, walrus и chained assignment запрещены.
  Runtime sandbox также не даёт `open`, `eval`, `exec`, `__import__`.
  Нужно формулировать как "обычный Python control flow с ограничениями DSL",
  а не "полный Python".
- В guide не вынесен список forbidden constructs. Он есть в
  `docs/python_dsl.md` и в коде, но пользователь интерактивного гайда его
  не увидит.
- Гайд говорит про "150+ команд". В текущем DSL auto-discovery даёт 74
  публичных CamelCase factory names и около 300 dispatch signatures в
  `COMMAND_REGISTRY`. Лучше писать: "74 пользовательские команды / фабрики,
  300 типизированных реализаций dispatch".

### §4: GeoGebra import

Покрыто:

- `.ggb` как ZIP с `geogebra.xml`.
- `loadGGB`, `strict`, `scene.geo.command_diagnostics`.
- `ggb_raw`, `ggb_style`, `elem.style`.
- `ImportPolicy`, `faithful`, `style_only`, mini-DSL
  `const/scale/quantize/remap`.
- `reloadPolicy` без повторного парсинга.
- `overlay.per_type` / `overlay.per_name` как слой поверх импорта.
- Честно указано, что интерактивный render-сервер гайда пока не умеет
  редактировать `.ggb`/policy из браузера.

Расхождения:

- В §4 сигнатура `loadGGB(...)` не включает `generate_stubs=True`, хотя
  текущий метод имеет параметр
  `loadGGB(filepath, style_file=None, px_size=None, import_policy=None,
  debug=False, generate_stubs=True, strict=False)`. В §11 это уже указано.
  Нужно синхронизировать §4.
- Описание `reloadPolicy` звучит как полноценная замена политики. Текущий код
  в `AnimaGeoScene.reloadPolicy` просто накладывает
  `import_policy.resolve_overrides_only(...)` поверх уже существующего
  `elem.ggb_style` и не пересоздаёт baseline из `ggb_raw`. Следствие: если
  первая policy задала `font_size_px`, а следующая задаёт только
  `stroke_width_px`, старый `font_size_px` останется. Либо нужно поправить код,
  либо в гайде явно написать, что `reloadPolicy` является layered override
  и не очищает прежние policy-ключи.
- В guide нет ссылки на `docs/archive/geogebra_command_audit.md`, где перечислены
  missing/partial GGB-команды (`IsTangent`, `Sector`, часть `Polar` и т.д.).
  Для пользователей `.ggb` это важнее, чем низкоуровневая структура ZIP.

### §5: стили

Покрыто:

- Новая схема `presets`, `defaults`, `overlay`, `rendering`, `import`.
- Приоритеты слоёв: explicit `elem.style` выше overlay, overlay выше
  import, import выше defaults.
- Deep-merge user JSON поверх builtin.
- Pixel-invariant `*_px`.
- `overlay.per_type`, `overlay.per_name`, `overlay.angle_radius`,
  `overlay.label_placement`.
- Разделение Python-кода внутри DSL и снаружи scene.

Расхождения:

- В статическом примере §5 используются:

  ```python
  self.setElementStyle('p', fill='...', fill_opacity=0.55)
  self.setElementStyle('alpha', fill='...', tick_count=2)
  ```

  Реальный метод `setElementStyle(names, ...)` итерирует `for name in names`.
  Для строки `'p'` это случайно работает, потому что строка односимвольная.
  Для `'alpha'` метод будет искать элементы `'a'`, `'l'`, `'p'`, `'h'`, `'a'`.
  Документация должна показывать `['p']` и `['alpha']`, либо код должен
  принимать single string и нормализовать в список.
- В §5 есть битая локальная ссылка `05-import-policy.html`. В `docs/guide`
  такого файла нет. Вероятно, ссылка должна вести на `04-geogebra.html#policy`
  или на `/style_guide/05-import-policy.html`.
- В §5 и §11 нужно единообразно закрепить, что automation-конфиги находятся
  в `overlay.angle_radius` и `overlay.label_placement`, а не в `rendering`.

### §6: подписи и автораскладка

Покрыто:

- `label_visible`, `label_text`, `label_mode`,
  `label_value_precision`, `label_angle_unit`, `label_color`,
  `label_anchor`, `label_offset_px`, `font_size_px`.
- 9-точечный anchor grid.
- TeX/Unicode conversion.
- One-shot `autoPlaceLabels()`, `label_placement_locked`.
- Split gaps для углов: `angle_gap_arc_px` и `angle_gap_sides_px`.
- `keyframe_snapshots` и `autoPlaceLabels(dynamic=True)`.

Что стоит уточнить:

- Default anchor описан как `rendering.label_anchor / BL`, а в
  `style/builtin.json` стоит `"label_anchor": "BC"`. При этом `GeoStyle`
  без user style фактически не переносит builtin `rendering.label_anchor` в
  `scene.style.rendering`, и `create_label` падает обратно в BL. Нужно
  выбрать одну модель: либо builtin действительно задаёт BC и переносится в
  render context, либо документы/`builtin.json` возвращаются к BL.
- Не описано, что bbox cache для TeX process-wide и очищается через
  `clear_bbox_cache()`/`resetScene()`. Это есть в `docs/gotchas.md`.

### §7: кривые

Покрыто:

- `Conic`, `Function`, `ImplicitCurve`.
- Conic classification, строковый parsing через sympy.
- Fill только для circle/ellipse conic.
- Dash только для circle-ветви conic.
- Function sampling, асимптоты, piecewise `If[...]`.
- ImplicitCurve через marching squares.
- Ограничения: кривые пока не учитываются как препятствия для label solver;
  tangent к Function/ImplicitCurve нет.

Соответствие коду хорошее. Важное уточнение: `Function(expr, var,
domain=(a,b))` действительно Python-only; guide это уже отмечает.

### §8-§9: анимации и экспорт

Покрыто:

- Разница SVG и MP4.
- `Show`, `Hide`, `Update`, `Shade`, `Restore`, `ShowCreate`.
- `play_keyframes`, JSON-format keyframes, easing.
- `addVar`, `addUpdater`, `clearUpdater`.
- `autoPlaceLabels(dynamic=True)` и label tracking.
- `exportSVG`, manim CLI, `px_size`, `ptUnit`, pixel-invariance.

Расхождения/нюансы:

- В §9 пример `Circle(O, r=2)` используется как объяснение math-radius, но
  DSL factory не принимает keyword `r`. Правильная пользовательская форма -
  `Circle(O, 2)`. В тексте можно оставить математическое обозначение, но не
  как кодовый пример.
- Guide не описывает `animating(tracker)` context manager, хотя он есть в API
  и reference.
- Не хватает явной связи с `docs/gotchas.md`: updater на самом
  анимируемом объекте не получает промежуточные значения; код решает это
  sentinel-объектом в `play_keyframes`.

### §10: рецепты

Покрыто:

- Типовые policy-рецепты для `.ggb`.
- Палитра, скрытие подписей, размеры точек/линий.
- Visual effects: anchor, multiple arcs, wave ticks, shade/restore, dash.
- Кривые и export recipes.
- В конце есть полезные gotchas.

Главный риск: рецепты смешивают канонические ключи и старые синонимы.
Например, в gotchas уже говорится `stroke_dash`, хотя runtime использует
`stroke_dash_ratio`. Нужно сделать рецепты строгими: только canonical keys.

### §11: Reference

Это самый проблемный раздел. Он нужен, но сейчас именно в нём больше всего
дрейфа.

Проблемные записи:

| В §11 | В текущем коде |
| --- | --- |
| `size` для point | `size_px` |
| `stroke_dash` | `stroke_dash_ratio` |
| `stroke_cap` | `stroke_linecap` |
| `right_mark` | `right_angle_marker` |
| `range_type` | `angle_range` (`minor` / `reflex`) |
| `lines` для angle/tick | `tick_count` |
| `lines_type` | `tick_style` |
| `r_offset` | скорее `label_radial_offset_px` для подписи; для радиуса дуги - `arc_size_px`/`arc_shift_px` |
| `defaults.angle.*` в таблице JSON reference | корректно, но automation `angle_radius` и `label_placement` должны быть под `overlay`, не под `rendering` |

Default-значения в таблице тоже местами устарели:

- `point_size.main` в builtin сейчас `6`, а не `2.83`.
- `line_width.main` в builtin сейчас `1.5`, а не `1`.
- `font_size.main` в builtin сейчас `14`, а не `10.5`.
- `defaults.angle.arc_size_px` в builtin идёт через
  `angle_radius.main = 17`, а не `10`.
- `rendering.label_anchor` в builtin `BC`, но фактический fallback без
  style-file остаётся BL через `create_label`.

Рекомендация: §11 лучше генерировать или хотя бы сверять с
`animageo/style/schema.py`, `animageo/style/builtin.json`,
`animageo/style/proxy.pyi` и `_build_render_ctx`.

## Что в гайде не описано или описано недостаточно

### 1. AI style-generation / construction summary

В коде есть полноценный exporter:

- `AnimaGeoScene.exportStylePromptSummary(filepath=None, **kwargs)`
- `animageo/exporters/construction_summary.py`
- `docs/construction_summary.md`
- `docs/ai_style_generation_context.md`
- `docs/ai_style_json_schema.json`

В `docs/guide` эта подсистема фактически отсутствует. Для текущей концепции
AnimaGeo это уже важный пользовательский сценарий: загрузить `.ggb`, получить
compact summary без сырого XML, передать LLM, получить style JSON и
опциональный DSL.

Нужен минимум отдельный раздел или recipe:

```python
scene.loadGGB("scene.ggb", style_file="base.json", px_size=[800, 600])
summary = scene.exportStylePromptSummary("scene.summary.json")
```

И таблица `include_geometry`, `include_ggb_style`, `include_style`,
`include_resolved_style`, `max_elements`, `style_keys`.

### 2. CLI `animageo`

README описывает:

```bash
animageo test.ggb -s default.json -px 240 auto
```

Код CLI находится в `animageo/__main__.py`. В `docs/guide` почти всё ведёт
пользователя через scene scripts и manim CLI, но не через пакетный CLI.
Для "первого результата из `.ggb` в SVG" это самый короткий путь.

### 3. Полная диагностика unsupported GeoGebra-команд

Guide говорит про `scene.geo.command_diagnostics`, но не показывает shape
diagnostic и не ссылается на command audit. Нужно добавить:

- пример структуры diagnostic;
- разницу root unsupported и dependency cascade;
- `strict=True`;
- ссылку на `docs/archive/geogebra_command_audit.md`.

### 4. DSL sandbox и ограничения

В guide есть предупреждение про `/render`, но не хватает developer-facing
ограничений DSL:

- imports удаляются;
- `global`, `nonlocal`, `+=`, walrus, chained assignment запрещены;
- некоторые builtins отсутствуют;
- lowercase forward-ref создаёт `Var(None)`;
- uppercase typo должен падать как ошибка.

Это важно для пользователей, которые будут переносить обычный Python-код в
`putCode`.

### 5. `resetScene`, state reuse и web-service сценарий

`loadGGB` теперь вызывает `resetScene`, чтобы повторные загрузки не
наслаивали конструкции. Это покрыто тестом `TestLoadggbStateReset`, но в
гайде не проговорено как API-свойство для сервисов, переиспользующих
`AnimaGeoScene`.

### 6. Точные field names и removed aliases

`docs/field_names.md` и `docs/gotchas.md` фиксируют, что старые короткие
поля (`.a`, `.c`, `.r`, `.v`, `.angle`, `.points`, `.end_points`) удалены.
В guide это не вынесено. Для пользователей старых версий нужен migration
callout.

### 7. Окружение Manim/Python

В текущей машине:

- `python3 -m pytest ...` падает, потому что Python 3.14 не имеет `manim`.
- `/opt/homebrew/opt/python@3.13/bin/python3.13 -m pytest ...` проходит.

В guide стоит явно писать: проверяйте `which python3.13`, `python3.13 -m pip
show manim`, и запускайте render/test тем Python, где установлен Manim.

## Концептуальные места, где guide и реализация расходятся

### Explicit style vs import style

Текущая концепция чистая:

1. `elem.style` - только explicit user writes / intrinsic flags.
2. `overlay.per_name` / `overlay.per_type` - project-level style.
3. `elem.ggb_style` - imported/adapted GGB baseline.
4. `defaults` - baseline.

В некоторых таблицах §11 ещё виден старый взгляд, где parser/runtime ключи
живут непосредственно как `elem.style`. Нужно удалить старые имена и не
называть import-layer "elem.style".

### Overlay automation location

`overlay.angle_radius` и `overlay.label_placement` концептуально верно лежат
в `overlay`, потому что это post-import automation, применимая и к GGB, и к
DSL. В §11 они попали в таблицу `rendering`, что возвращает старую модель.

### `reloadPolicy` как "замена"

Если оставить текущий код, `reloadPolicy` - не "replace policy", а "apply
additional import-policy overrides". Это важно для UI: кнопка "заменить
политику" должна либо сначала восстановить faithful baseline, либо явно
показывать накопительное поведение.

### Batch API принимает list, guide иногда показывает string

`setElementStyle` и `setVisible` концептуально пакетные. Реализация не
нормализует single name. Guide должен не провоцировать single-string usage,
или код должен принять `str` как один name.

## Приоритетные правки

1. Исправить §11 reference:
   `size_px`, `stroke_dash_ratio`, `stroke_linecap`, `right_angle_marker`,
   `angle_range`, `tick_count`, `tick_style`, актуальные builtin defaults.
2. Убрать `overlay.angle_radius`/`overlay.label_placement` из таблицы
   `rendering` в §11; оставить их только под `overlay`.
3. Исправить §5 `setElementStyle('alpha', ...)` на
   `setElementStyle(['alpha'], ...)` или обновить код API для single string.
4. Исправить битую ссылку `docs/guide/05-styles.html -> 05-import-policy.html`.
5. Синхронизировать сигнатуру `loadGGB` в §4 с `generate_stubs=True`.
6. Описать реальное поведение `reloadPolicy` или изменить код, чтобы policy
   действительно заменялась.
7. Добавить в guide короткий раздел/recipe про
   `exportStylePromptSummary` и AI style-generation pipeline.
8. Добавить CLI-путь `animageo file.ggb ...` в §2 или §9.
9. Добавить callout "DSL is Python-like, not unrestricted Python" со списком
   запрещённых constructs и ссылкой на `docs/python_dsl.md`.
10. Добавить ссылку на `docs/archive/geogebra_command_audit.md` из §4.

## Проверочные заметки

- Интерактивные примеры `docs/guide` сейчас не ломаются: 26/26 render OK.
- Проверенный тестовый срез: 67 tests OK на Python 3.13.
- Обнаружена одна битая локальная ссылка в HTML guide:
  `docs/guide/05-styles.html: href="05-import-policy.html"`.
- Рабочее дерево на момент аудита уже было dirty; отчёт оценивает текущую
  рабочую версию, а не последний commit.
