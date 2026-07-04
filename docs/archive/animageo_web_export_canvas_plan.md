# План для animageo_web: настройки экспорта и согласование с animageo

## Цель

В веб-сервисе нужно реализовать пользовательскую модель экспорта, не смешивая
ее со style JSON библиотеки. Пользователь должен отдельно управлять:

- эталонным холстом, под который рассчитан стиль;
- физическим размером итогового SVG/PNG/MP4;
- способом размещения reference canvas внутри export canvas.

Библиотека `animageo` предоставляет низкоуровневый API, а web владеет:

- UI;
- export presets;
- сохранением `default_export_config`;
- task config;
- bulk export;
- animation export;
- MP4 quality/fps;
- отображением результатов и metadata.

## Новая модель данных

Добавить в task/export config объект:

```json
{
  "export_layout": {
    "mode": "reference_canvas",
    "reference_size": [300, 220],
    "export_size": [1920, 1080],
    "fit": "contain",
    "source_rect": "ggb_view",
    "scale": null,
    "anchor": "center",
    "offset": [0, 0]
  }
}
```

Старый формат оставить:

```json
{
  "px_size": [800, "auto"]
}
```

Правило совместимости:

- если `export_layout.mode == "reference_canvas"` - использовать новый API
  библиотеки;
- иначе использовать legacy `px_size`.

## Backend API

Расширить схемы:

- `app/schemas/construction.py::ExportRequest`
- `app/routers/constructions.py::BulkExportRequest`
- `app/schemas/animation.py::AnimationExportRequest`
- `app/schemas/export_preset.py`
- `Construction.default_export_config`
- `ExportPreset.config`

Рекомендуемые Pydantic-типы:

```python
from typing import Literal, Any
from pydantic import BaseModel, Field

PxValue = int | float | Literal["auto"]

class ExportLayoutConfig(BaseModel):
    mode: Literal["legacy_px_size", "reference_canvas"] = "legacy_px_size"
    reference_size: list[float] | None = None
    export_size: list[PxValue] | None = None
    fit: Literal["contain", "cover", "width", "height", "none", "manual"] = "contain"
    source_rect: Literal["ggb_view", "rendered_bounds"] = "ggb_view"
    bounds_padding: float = 0
    infinite_policy: Literal["clip", "ignore"] = "ignore"
    scale: float | None = None
    anchor: Literal[
        "top_left", "top", "top_right",
        "left", "center", "right",
        "bottom_left", "bottom", "bottom_right",
    ] = "center"
    offset: list[float] = Field(default_factory=lambda: [0, 0])
```

`rendered_bounds` можно использовать как библиотечный режим автовписывания
фактического чертежа по итоговым mobject bounds. Не предлагать `stretch` и
arbitrary explicit rect, пока библиотека не поддерживает их полностью.

## Backend adapter к библиотеке

Создать единый helper, например:

`app/services/export_layout_config.py`

```python
def load_scene_with_export_config(
    scene,
    *,
    ggb_path: str,
    style_path: str | None,
    config: dict,
    generate_stubs: bool = False,
):
    layout = config.get("export_layout") or {}
    if layout.get("mode") == "reference_canvas":
        export_size = layout.get("export_size") or config.get("px_size") or [800, "auto"]
        scene.loadGGB(
            ggb_path,
            style_file=style_path,
            reference_size=layout.get("reference_size"),
            export_size=export_size,
            export_fit=layout.get("fit", "contain"),
            export_source_rect=layout.get("source_rect", "ggb_view"),
            export_scale=layout.get("scale"),
            export_anchor=layout.get("anchor", "center"),
            export_offset=layout.get("offset", [0, 0]),
            export_bounds_padding=layout.get("bounds_padding", 0),
            export_infinite_policy=layout.get("infinite_policy", "ignore"),
            generate_stubs=generate_stubs,
        )
    else:
        scene.loadGGB(
            ggb_path,
            style_file=style_path,
            px_size=config.get("px_size", [800, "auto"]),
            generate_stubs=generate_stubs,
        )
```

Заменить прямые вызовы `scene.loadGGB(... px_size=...)` в:

- `app/services/conversion.py`
- `app/workers/convert.py`
- `app/services/animation_export.py`
- `app/services/dsl_runtime.py` для preview/export-сценариев
- `app/services/style_preview.py`, если preview должен показывать
  `canvas.reference`
- `app/services/thumbnails.py`, если thumbnails должны использовать новый
  layout или явно остаться legacy thumbnails

## SVG/PNG export

Для SVG:

- `scene.exportSVG()` должен получить SVG physical size из `export_size`.
- background handling оставить web-ответственностью.

Для PNG:

- SVG -> PNG через CairoSVG должен сохранять `export_size`;
- если CairoSVG получает SVG с правильными `width/height`, отдельный resize
  не нужен;
- добавить тест, что PNG dimensions соответствуют `export_layout.export_size`.

## MP4 export

Критично: Manim берет physical video size из `manim.config`, а не из
`scene.style.export`.

Для любого MP4 export:

1. вычислить concrete `export_size`;
2. вставить в generated scene до импорта/создания scene:

```python
from manim import config as _manim_config
_manim_config.pixel_width = 1920
_manim_config.pixel_height = 1080
```

3. затем вызвать `scene.loadGGB(... export_size=[1920,1080], ...)`.

`quality` должен управлять Manim preset/fps/encoding profile, но не должен
молча переопределять выбранный пользователем `export_size`.

Обновить:

- `app/services/conversion.py::_render_static_mp4`
- `app/services/animation_export.py::_generate_animation_scene`
- celery path `app/workers/convert.py::render_video`
- celery path `app/workers/convert.py::render_animation`

## Frontend UI

Основной экран: `frontend/src/components/editor/ExportPanel.vue`.

Добавить явное разделение:

### Эталонный холст

Опции:

- "Из GeoGebra/style" - default;
- "Свой размер" - поля width/height;
- в будущем: "из сохраненного style.canvas.reference".

### Размер экспорта

Текущие HD/FHD/4K/A4/custom оставить, но это уже `export_size`, а не
`px_size`.

### Размещение

Опции:

- `contain` - вписать целиком;
- `cover` - заполнить с возможной обрезкой;
- `width` - по ширине;
- `height` - по высоте;
- `none` - вставить как есть;
- `manual` - ручной коэффициент.

Advanced:

- anchor;
- offset x/y;
- manual scale.

UI copy:

> Эталонный холст определяет масштаб стиля. Размер экспорта определяет размер
> итогового файла.

## Frontend state и API clients

Обновить:

- `frontend/src/views/EditorView.vue`
- `frontend/src/components/editor/ExportPanel.vue`
- `frontend/src/utils/render.ts`
- `frontend/src/utils/renderOptions.ts`
- `frontend/src/api/constructions.ts`
- `frontend/src/api/animations.ts`
- `frontend/src/api/exportPresets.ts`
- bulk export in `frontend/src/views/ProjectView.vue`

Добавить helper:

```ts
function currentExportLayout(): ExportLayoutConfig | null
```

`currentExportSnapshot()` должен сохранять:

```ts
{
  output_format,
  px_size,          // legacy fallback
  export_layout,    // new model
  background,
  fps,
  quality,
  style_id
}
```

`applyPreset()` должен уметь прочитать и старый `px_size`, и новый
`export_layout`.

## Export presets

Сохраненные export presets должны хранить весь `export_layout`.

Backward compatibility:

- старые presets с `px_size` продолжают применяться;
- при сохранении нового preset писать и `export_layout`, и legacy `px_size`
  как fallback для старых задач/клиентов.

## Results, gallery, shared view

Обновить отображение metadata:

- `frontend/src/components/editor/ExportResults.vue`
- `frontend/src/views/SharedConstructionView.vue`
- gallery/public render metadata, если использует `task.config`

Правила:

- если есть `config.export_layout.export_size`, показывать его как размер;
- если есть `reference_size`, показывать `ref 300×220`;
- показывать `fit: contain/cover/...` в компактном виде;
- если нового layout нет, fallback на `config.px_size`.

## Style editor и style preview

Не переносить export settings в `rendering`.

В style editor:

- убрать или пометить `rendering.scale_export` как legacy;
- не предлагать `scale_export` как основной способ высокого качества;
- при необходимости добавить `canvas.reference` как style metadata:

```json
{
  "canvas": {
    "reference": {
      "width": 300,
      "height": 220,
      "source": "ggb_view"
    }
  }
}
```

Style preview может использовать `canvas.reference`, но export panel всегда
должна владеть final export settings.

Обновить:

- `frontend/src/components/editor/style-editor/styleConfig.ts`
- `frontend/src/components/editor/style-editor/types.ts`
- `StyleEditorRenderingPanel.vue`
- docs `docs/style-editor.md`
- backend `app/services/style_migration.py`

## Миграция и совместимость

Не нужна обязательная DB migration для старых task configs: они могут жить с
`px_size`.

Нужна мягкая миграция при чтении:

- если `export_layout` отсутствует, считать config legacy;
- если старый preset содержит `px_size`, UI показывает его как export size
  в legacy mode;
- новые presets сохранять в новом формате.

## Тесты

Backend:

- request schemas принимают `export_layout`;
- legacy `px_size` продолжает работать;
- conversion helper вызывает `scene.loadGGB` с `export_size/reference_size`
  для нового режима;
- SVG task пишет correct `task.config`;
- bulk export переносит `export_layout` во все tasks;
- static MP4 generated scene выставляет `_manim_config.pixel_width/height`;
- animation MP4 generated scene выставляет `_manim_config.pixel_width/height`;
- export presets сохраняют и возвращают `export_layout`.

Frontend:

- `resolveExportSize`/новый helper корректно формирует `export_layout`;
- `ExportPanel` переключает reference/export settings;
- `applyPreset` читает старый и новый формат;
- `ExportResults` показывает metadata нового формата;
- `SharedConstructionView` вычисляет preview canvas из `export_layout.export_size`.

Manual QA:

1. Конструкция с исходным видом около 300px экспортируется в 1920×1080 и
   визуально масштабируется целиком.
2. Та же конструкция в legacy `px_size=[1920,1080]` сохраняет старое поведение
   с мелкими pixel-invariant стилями.
3. Bulk export нескольких маленьких конструкций в FHD дает одинаковую
   физическую canvas size и ожидаемый fit.
4. MP4 output реально имеет выбранное разрешение, проверять через ffprobe.
5. Старые export presets и старые completed tasks продолжают отображаться.

## Acceptance criteria

- Web UI разделяет "эталонный холст" и "размер экспорта".
- Style JSON не используется для хранения final export settings.
- Все новые export settings сохраняются в task config и export preset.
- SVG/PNG/MP4 используют один и тот же export-layout config.
- MP4 physical resolution совпадает с `export_layout.export_size`.
- Legacy `px_size` полностью совместим.
- Библиотека `animageo` используется только через публичный API, без web
  monkeypatches внутрь renderer.
