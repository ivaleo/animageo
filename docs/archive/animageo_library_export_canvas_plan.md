# План для библиотеки animageo: reference canvas vs export canvas

## Цель

Библиотека `animageo` не должна владеть продуктовой моделью экспорта веб-сервиса:
пресетами, UI-настройками, пользовательскими сценариями, качеством MP4,
историей задач и хранением конфигов. Ее роль - предоставить стабильный
низкоуровневый интерфейс, который позволяет потребителю разделить:

- reference/source canvas: исходный холст, под который рассчитан стиль;
- export canvas: физический размер итогового SVG/PNG/MP4;
- layout transform: как reference canvas размещается внутри export canvas.

## Что оставить

Оставить отдельный модуль расчета layout:

- `animageo/export_layout.py`
- `ExportLayout`
- `compute_export_layout(...)`

Это правильный библиотечный уровень: чистая функция, без web-состояния,
без БД, без пользовательских пресетов.

Оставить новый API в `AnimaGeoScene`:

```python
scene.loadGGB(
    ggb_path,
    style_file=style_path,
    reference_size=[300, 220],
    export_size=[1920, 1080],
    export_fit="contain",
    export_source_rect="ggb_view",
    export_scale=None,
    export_anchor="center",
    export_offset=[0, 0],
)
```

Оставить legacy-путь `px_size` без изменения поведения. Это важно для
совместимости существующих скриптов, документации и web-задач.

Оставить внутреннее разделение:

- `ptUnit` - финальный масштаб export/camera/SVG transform;
- `ptUnit_style` - reference-масштаб для визуальных `*_px`;
- `ptUnit_ggb` - исходный GeoGebra scale для GGB label offsets.

Оставить тесты:

- unit-тесты `compute_export_layout`;
- integration-тесты, что `export_size` не ломает legacy `px_size`;
- integration-тесты, что `stroke_width_px`, `size_px`, `font_size_px`,
  `arc_size_px` считаются через `ptUnit_style`.

## Что не вшивать в библиотеку

Не добавлять в библиотеку web-понятия:

- пользовательские export presets;
- product-tier ограничения;
- UI labels;
- сохранение настроек экспорта;
- дефолтные web-пресеты HD/FHD/4K/A4/social;
- очереди задач;
- S3 paths;
- background/quality/fps как web-модель.

Не переносить реальные настройки конкретного экспорта в style JSON.

Допустимое исключение: `canvas.reference` как metadata стиля для preview и
style-authoring. Но `export_size`, `fit`, `anchor`, `quality`, `fps`,
`background` должны передаваться отдельно от style JSON.

## Что доделать в библиотеке

### 1. Уточнить публичный контракт

Документировать, что:

- `px_size` - legacy режим: размер холста и визуальный scale связаны;
- `export_size/reference_size` - новый режим: reference scale и physical output
  разделены;
- при одновременной передаче `px_size` и `export_size` приоритет у
  `export_size`, а `px_size` используется только как fallback export size,
  если `export_size` не задан.

### 2. Уточнить `source_rect`

Поддержанные режимы:

1. `ggb_view` - использовать исходный GeoGebra viewport и позиционирование.
2. `rendered_bounds` - двухпроходно измерить bounds видимых итоговых
   mobject-ов в исходном масштабе и вписать уже этот прямоугольник.

Для `rendered_bounds` есть параметры:

- `export_bounds_padding` - отступ в source-пикселях;
- `export_infinite_policy='ignore'|'clip'` - как учитывать `Line`/`Ray`;
  дефолт `ignore`.

Не реализованы и не обещаются:

- `style_reference` как отдельный source-rect;
- `explicit` rect `{width,height,xZero,yZero,ptUnit}`;
- неравномерный `stretch`.

### 3. Не обещать `stretch`

Не добавлять неравномерный `stretch`, пока renderer построен вокруг одного
`ptUnit`.

Если когда-либо понадобится `stretch`, это отдельный проект:

- `ptUnitX`, `ptUnitY`;
- пересмотр stroke/font/labels;
- решение, искажается ли геометрия или только viewport;
- отдельные visual-regression tests.

### 4. MP4 контракт

Библиотека может только выставить camera frame согласно `style.export`.
Физический размер MP4 задает Manim `config.pixel_width/pixel_height`.

Нужно явно записать в docs:

- для MP4 потребитель обязан выставить Manim config в размер `export_size`;
- библиотека не должна угадывать web-quality preset.

### 5. Проверить все visual conversions

Провести audit всех мест, где визуальные пиксели делятся на scale:

- `_build_render_ctx`;
- `_render_angle`;
- `_render_point`;
- label placement;
- dynamic labels/keyframes;
- grid/axis helpers;
- curve sampling, где шаг в пикселях может логически относиться к output
  `ptUnit`, а не к `ptUnit_style`.

Разделить на две категории:

- visual style sizes: `ptUnit_style`;
- render sampling/output density: вероятно `ptUnit`.

### 6. Документация

Оставить в library docs раздел:

- "Reference canvas vs export canvas";
- "Legacy px_size";
- "How web services should call this API";
- "What belongs to style JSON and what does not".

Убрать формулировки, где `rendering.scale_export` выглядит как основной
современный способ экспорта. Оставить его как legacy alias/backward compatible.

## Acceptance criteria

- Все существующие тесты библиотеки проходят.
- `px_size=[800,600]` ведет себя как раньше.
- `reference_size=[300,150]`, `export_size=[1200,600]`, `fit="contain"`
  дает `contentScale=4`, `ptUnit=source_ptUnit*4`, `ptUnit_style=source_ptUnit`.
- SVG имеет physical size `export_size`.
- Визуальные `stroke_width_px`, `font_size_px`, `size_px` масштабируются вместе
  с reference canvas при новом export-layout.
- Style JSON не содержит обязательных export-полей.
