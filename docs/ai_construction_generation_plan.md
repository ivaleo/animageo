# AI Creation And Editing Of Constructions

Статус: проработка второго этапа AI-пайплайна, 2026-05-11.

Цель этапа --- научить AI не только подбирать стиль, но и создавать или
редактировать геометрическую конструкцию AnimaGeo так, чтобы результат можно
было машинно проверить и безопасно передать в текущий runtime.

Документ фиксирует текущее состояние библиотеки и рабочий план. Он не является
готовым prompt-контекстом для модели; такой компактный контекст нужно собрать
после реализации валидатора и edit-summary.

## Главный Вывод

Обменный формат для AI-конструкций сейчас должен быть AnimaGeo Python DSL,
совместимый с `scene.putCode(...)` / `scene.loadCode(...)`.

Не стоит просить модель генерировать внутренний JSON графа `Construction`:

- внутренние классы и `Command` не являются стабильным внешним форматом;
- DSL уже регистрирует элементы, зависимости, tuple-output команды и стили;
- DSL умеет ссылаться на элементы, загруженные из `.ggb`;
- DSL можно прогнать через существующий AST-transform и собрать диагностику;
- пользовательский результат остается читаемым и редактируемым вручную.

`animageo-construction-summary/v1` остается входным контекстом для модели. Он
помогает выбрать существующие элементы и понять зависимости, но не должен
становиться форматом восстановления всей конструкции.

## Текущая Основа В Библиотеке

### DSL

Актуальная точка входа:

```python
scene.putCode(code)
scene.loadCode("patch.py")
```

`engine='exec'` является текущим поведением. В AI-контракте лучше не заставлять
модель писать аргумент `engine`.

Поддерживается нормальный Python поверх геометрических фабрик:

- `for`, `if`, `while`, `def`, comprehensions, lambda;
- kwargs, включая `name=`;
- f-строки;
- tuple-unpack для команд с несколькими выходами;
- арифметика на proxy-элементах;
- доступ к живым полям через `ElementProxy`;
- helpers `style(...)`, `hide(...)`, `show(...)`;
- `elem.style.key = value` и `elem.style["key"] = value`.

На 2026-05-11 auto-discovery видит 87 публичных CamelCase-фабрик и 367
dispatch-сигнатур из `animageo/geo/lib_commands.py`.

Ключевые группы фабрик:

- базовые объекты: `Point`, `Line`, `Segment`, `Ray`, `Circle`, `Arc`,
  `CircleSector`, `Angle`, `Polygon`, `Vector`, `Conic`, `Function`,
  `ImplicitCurve`;
- производные объекты: `Midpoint`, `Intersect`, `Center`, `Vertex`, `Focus`,
  `Axes`, `Directrix`, `Tangent`, `Polar`;
- измерения и предикаты: `Distance`, `Length`, `Radius`, `Area`, `Perimeter`,
  `Circumference`, `AreCollinear`, `AreParallel`, `ArePerpendicular`;
- преобразования: `Rotate`, `Translate`, `Reflect` / `Mirror`;
- коники: `Ellipse`, `Hyperbola`, `Parabola`, `Incircle`;
- алиасы GeoGebra: `CircularArc`, `CircularSector`,
  `CircumcircularArc`, `CircumcircularSector`,
  `PerpendicularLine`, `PerpendicularBisector`.

Полный актуальный список должен извлекаться программно из
`animageo.parsers.dsl.namespace._DISCOVERED_COMMANDS` и
`animageo.geo.lib_commands.list_commands()`, а не поддерживаться руками в
prompt.

### Namespace И Имена

Правила разрешения имен важны для AI-редактирования:

- CamelCase-имя становится фабрикой, если для него есть dispatch в
  `lib_commands.py`;
- существующее имя элемента из загруженной конструкции становится
  `ElementProxy`;
- неизвестное lowercase-имя создает forward-ref `Var(None)`;
- неизвестная CamelCase-команда должна приводить к ошибке, а не к догадке.

Имена, пришедшие из `.ggb` или раннего DSL, можно использовать прямо в patch
DSL:

```python
# После scene.loadGGB("input.ggb")
M = Midpoint(A, B)
hide(aux_line)
style(M, fill="#d62728", label_visible=True)
```

AI не должен придумывать существующие имена. Для patch-edit он обязан брать
имена из construction summary или из предоставленного исходного DSL.

### Редактирование Существующей Конструкции

Текущее поведение `loadCode` после `loadGGB` или предыдущего `putCode`:

- добавление новых элементов безопасно;
- `hide(...)` / `show(...)` меняют `elem.visible`;
- `style(...)` и `elem.style` пишут в explicit style layer;
- повторное top-level присваивание существующему имени переопределяет элемент:
  старый binding удаляется из graph/state, новый элемент получает то же имя,
  downstream-зависимости пересчитываются после rebuild.

Пример осознанного переопределения:

```python
# Было E из исходной конструкции. Теперь E становится поворотом D вокруг O.
E = Rotate(D, 35 * pi / 180, O)
```

Такой edit нужно считать сильной операцией: она меняет смысл узла и может
изменить все downstream-элементы. AI должен делать это только когда запрос
явно просит изменить построение существующего объекта.

Безопасного публичного delete API пока нет. До его появления удаление в
AI-редактировании нужно представлять как `hide(...)`, либо как replacement DSL
для полностью DSL-owned сцены.

### Construction Summary

`scene.exportStylePromptSummary(...)` и
`animageo.exporters.construction_summary` уже дают полезную основу:

- `schema`, `source`, `viewport`;
- имена, типы, visibility, label visibility;
- `construction.command`, `inputs`, `outputs`;
- компактную геометрию;
- `ggb_style`, selected raw GGB summary;
- diagnostics.

Для полноценного AI-editing этого недостаточно. Нужен расширенный prompt
payload или новая опция summary, которая добавит:

- источник редактирования: `ggb`, `dsl_file`, `dsl_inline`, `summary_only`;
- исходный DSL, если он доступен и его можно редактировать как source of truth;
- dependency graph: parents, children, downstream count;
- список root/free elements, которые допустимо двигать;
- список named outputs, которые пользователь ожидает сохранить;
- command inventory/affordances для текущей версии;
- сведения о неподдержанных или unbuilt элементах;
- policy по коллизиям имен и переопределению;
- признаки, что элемент импортирован из GGB и не имеет round-trip DSL.

## Режимы AI-Работы

### 1. Создание С Нуля

Вход:

- пользовательское описание;
- краткий DSL-контекст и список поддержанных фабрик;
- опционально style context/schema, если запрошен внешний вид.

Выход:

- полный `construction_dsl`;
- опциональный style JSON по существующему style-контракту;
- notes с допущениями.

AI создает самодостаточный body для `scene.putCode(...)`. Он не должен писать
`AnimaGeoScene`, `construct`, `loadGGB`, `showAllGeometry`, render/export или
файловые операции.

Минимальный пример:

```python
A = Point(0, 0)
B = Point(5, 0)
C = Point(1.5, 3)

base, ab, bc, ca = Polygon(A, B, C)
M = Midpoint(A, B)
median = Segment(C, M)

style(A, B, C, fill="#1f77b4", label_visible=True)
style(median, stroke="#d62728", stroke_width_px=3)
```

### 2. Patch-Edit Поверх GGB

Вход:

- исходный `.ggb` уже загружен сервером;
- модель получает construction summary;
- модель получает пользовательский запрос на изменение.

Выход:

- patch DSL, который выполняется после `scene.loadGGB(...)`;
- опциональный style JSON, если изменение лучше выразить через style layer;
- notes о затронутых именах.

Разрешенные операции:

- добавить новые элементы от существующих;
- показать/скрыть существующие элементы;
- записать explicit style на конкретные элементы;
- добавить вычисляемые переменные и производные объекты;
- переопределить существующее имя только при явном structural edit.

Неразрешенные операции в текущей версии:

- физически удалить импортированный GGB-элемент;
- переименовать элемент без новой публичной операции rename;
- восстанавливать всю конструкцию из summary;
- редактировать сырой `.ggb` XML.

### 3. Patch-Edit Поверх DSL

Если исходный DSL доступен и считается source of truth, есть два варианта:

- `patch`: добавить короткий DSL после исходника;
- `replace`: вернуть полный новый DSL, если запрос меняет структуру сцены.

`patch` предпочтителен для добавления вспомогательных построений, подписей,
видимости и локальных стилей. `replace` нужен, когда пользователь просит
перестроить конструкцию, переименовать элементы или удалить узлы.

### 4. Summary-Only Edit

Если есть только summary без исходного `.ggb` и без исходного DSL, AI может
делать только patch by name. Он не может честно сгенерировать полную замену
конструкции, потому что summary намеренно теряет часть информации.

## Output Contract Для Модели

Для веб-сервиса лучше использовать JSON-wrapper, чтобы не парсить свободный
Markdown:

```json
{
  "schema": "animageo-ai-construction-response/v1",
  "mode": "create",
  "construction_dsl": "A = Point(0, 0)\nB = Point(4, 0)\n...",
  "style": null,
  "notes": [
    "Assumed triangle side length 4 because the request did not specify scale."
  ]
}
```

`mode`:

- `create` --- полный DSL для пустой конструкции;
- `patch` --- DSL, который запускается после `loadGGB` или исходного DSL;
- `replace` --- полный replacement DSL для DSL-owned сцены.

Если в UI удобнее Markdown, секции должны быть строго фиксированы:

````markdown
CONSTRUCTION_DSL:
```python
A = Point(0, 0)
B = Point(4, 0)
```

STYLE_JSON:
```json
null
```

NOTES:
- ...
````

`STYLE_JSON` должен оставаться в уже существующем контракте
`docs/ai_style_generation_context.md`. Структурные изменения конструкции не
нужно маскировать style JSON. И наоборот: если задача чисто визуальная,
лучше возвращать style JSON без DSL.

## Правила Генерации DSL

AI должен:

- писать только body для `scene.putCode(...)` / `scene.loadCode(...)`;
- использовать только текущие CamelCase-фабрики и helpers `style`, `hide`,
  `show`;
- использовать точные имена полей из `docs/field_names.md`;
- задавать стабильные имена через `name=` внутри функций и циклов;
- использовать tuple-unpack для multi-output команд;
- явно объявлять `deg = pi / 180`, если нужны градусы;
- выбирать читаемые имена латиницей, без leading underscore;
- не создавать скрытые "магические" точки без причины;
- скрывать вспомогательные объекты через `hide(...)`, если они не должны
  отображаться;
- оставлять `notes`, когда запрос неоднозначен или требует неподдержанной
  операции.

AI не должен:

- писать `import`, `from import`, `open`, `eval`, `exec`, `compile`;
- обращаться к файловой системе, сети, manim scene или renderer;
- использовать private/dunder API;
- генерировать raw `Command(...)` или напрямую менять `Construction`;
- полагаться на несуществующие short aliases полей;
- использовать старые style-ключи без `_px`, например `line_width` или
  `font_size`;
- физически удалять/переименовывать GGB-элементы;
- переопределять существующее имя без явного намерения.

## Когда Стиль, А Когда Конструкция

AI должен разделять две задачи:

- внешний вид: color, width, opacity, label, z-index, import-policy,
  per-type/per-name rules --- это style JSON или explicit `elem.style`;
- геометрический смысл: точки, линии, зависимости, пересечения, медианы,
  касательные, преобразования --- это construction DSL.

Если нужно сохранить GeoGebra-внешний вид, используется style/import layer:
`import.enabled=true`, `ggb_style` остается в resolver chain. Если нужно
полностью свой внешний вид, отключается import layer и переопределяются только
нужные defaults/overlay, а не переписываются все GGB-значения.

Для construction-edit аналогичное правило:

- если нужно добавить поверх импортированной GGB-сцены, пишется patch DSL;
- если нужно заменить авторское построение, нужен DSL-owned source или явный
  replacement mode;
- если нужно только спрятать/подсветить, это visibility/style, а не
  перестройка геометрии.

## Валидационный Пайплайн

Минимальный pipeline для AI-конструкций:

1. Нормализовать ответ модели: достать JSON-wrapper или фиксированные секции.
2. Проверить `mode`, наличие `construction_dsl`, тип `style`, обязательные
   `notes`.
3. Статически распарсить DSL через `ast.parse`.
4. Запустить существующий DSL transform и получить `DSLSyntaxError` с line/col.
5. Дополнительно запретить scene/render/file/network/private patterns на уровне
   AST, даже если Python runtime их пока не достигнет.
6. Выполнить DSL в isolated subprocess с лимитами CPU, memory и wall-clock.
7. Для patch режима загрузить исходную конструкцию, затем применить patch.
8. Сделать `rebuild(full=True)`.
9. Собрать diagnostics: исключения, unbuilt visible outputs, missing names,
   collision/redefinition report.
10. Экспортировать summary результата и проверить базовые ожидания: появились
    заявленные элементы, имена уникальны, нет пустых видимых элементов.
11. Если есть style JSON, проверить его через `docs/ai_style_json_schema.json`.
12. Опционально сделать render smoke test для SVG/PNG и bbox.

Soft sandbox в DSL не является security boundary. Для веб-сервиса выполнение
непроверенного AI DSL обязательно должно идти в отдельном процессе с
изоляцией ресурсов и файловой системы.

## Диагностика И Repair Loop

В prompt repair-loop модели нужно отдавать не traceback целиком, а короткий
машинный отчет:

```json
{
  "error_type": "dsl_syntax",
  "line": 7,
  "column": 5,
  "message": "import statements are not allowed",
  "known_names": ["A", "B", "C", "circ"],
  "known_factories": ["Point", "Line", "Circle", "Intersect"]
}
```

Для runtime ошибок полезны:

- unknown factory;
- unknown existing name;
- name collision;
- redefinition of imported name;
- unsupported command dispatch;
- unbuilt output;
- style schema error.

Repair prompt должен просить вернуть весь исправленный artifact, а не diff,
пока нет собственного patch-протокола.

## Необходимые Реализации

### P0. Документация И Контекст

- Зафиксировать этот план в roadmap.
- Собрать отдельный `ai_construction_generation_context.md` для модели:
  компактнее этого документа, без внутренних рассуждений.
- Сгенерировать машинный command inventory из текущей версии.
- Подготовить 10-20 эталонных prompt/answer примеров.

### P1. Response Parser И Validator

- JSON-wrapper schema: `animageo-ai-construction-response/v1`.
- Markdown fallback parser для секций `CONSTRUCTION_DSL`, `STYLE_JSON`,
  `NOTES`.
- AST/DSL validation без исполнения.
- Запрет scene/file/network/private API.
- Style JSON validation через текущую schema.

### P2. Isolated Execution

- subprocess runner для DSL;
- wall-clock timeout;
- memory/CPU limits, насколько это переносимо;
- scratch workspace;
- structured diagnostics.

### P3. Edit Summary

Расширить construction summary или добавить отдельный режим:

- dependency graph;
- root/free elements;
- editable/imported/source-owned flags;
- downstream impact;
- original DSL source metadata;
- command inventory reference;
- unsupported/unbuilt diagnostics.

### P4. Patch API

Добавить публичную обертку уровня scene:

```python
result = scene.applyConstructionPatch(
    code,
    mode="patch",
    validate=True,
)
```

Она должна вернуть structured report: added, redefined, hidden, shown, styled,
diagnostics, summary_after.

### P5. Delete/Rename Strategy

Решить отдельно, нужны ли публичные операции:

- `deleteElement(name, cascade=False)`;
- `renameElement(old, new)`;
- `replaceElement(name, code_or_command)`.

Без этого AI не должен обещать настоящее удаление или переименование поверх
импортированной GGB-сцены.

### P6. Optional Operations JSON

Если DSL окажется слишком свободным для UI/editing, можно добавить более
строгий operation format:

```json
[
  {"op": "add", "code": "M = Midpoint(A, B)"},
  {"op": "hide", "names": ["aux1"]},
  {"op": "style", "names": ["M"], "props": {"fill": "#d62728"}}
]
```

Но это должно быть надстройкой над DSL, а не заменой DSL на внутренний graph
JSON.

## Риски

- Геометрический язык пользователя часто неоднозначен: "построй высоту" требует
  выбора вершины и стороны.
- Summary-only контекст недостаточен для полного round-trip.
- Переопределение имен может неожиданно изменить downstream.
- Удаление и rename пока не имеют публичной безопасной семантики.
- DSL является полноценным Python-subset и требует process isolation.
- Модель может галлюцинировать команды GeoGebra, которых нет в AnimaGeo.
- Часть GeoGebra-команд остается неполной: точный symbolic `Locus`,
  `LocusEquation`, `RadicalAxis`, `Power`, `Curvature` и близкие
  специализированные команды.
- 3D, списки, изображения, регионы и часть CAS-поведения не являются текущей
  целевой областью.

## Критерии Готовности Этапа

Этап можно считать рабочим, когда:

- есть компактный AI context для construction generation/editing;
- есть schema/validator для ответа модели;
- patch DSL проверяется без исполнения и затем исполняется в isolated runner;
- по результату формируется structured diagnostics;
- есть regression corpus на create, GGB patch, DSL patch, ambiguous request,
  unsupported request, bad command, name collision;
- roadmap явно различает style-generation и construction-generation.
