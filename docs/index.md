# AnimaGeo — документация

**GeoGebra → Python → Manim → SVG / MP4**

AnimaGeo превращает геометрические конструкции GeoGebra в качественные
изображения и анимации: парсит `.ggb`, строит граф зависимостей между
элементами, рендерит через manim и экспортирует в SVG (Cairo), PDF/EPS, TikZ,
интерактивный JSXGraph или видео (MP4/GIF/WebM/PNG). Конструкции можно также
строить напрямую на встроенном Python-DSL, без GeoGebra-файла.

## Начало работы

- [Быстрый старт](quickstart.md) — установка, первый рендер, CLI и код
- [Архитектура](architecture.md) — пайплайн и карта модулей
- [../README.md](../README.md) — обзор проекта и возможностей

## Справочники

- [Справочник API](api.md) — методы сцены и конструкции
- [Keyframe-анимации](keyframes.md) — JSON/timeline формат `play_keyframes`, v2 стили/видимость/камера/events
- [Python DSL](python_dsl.md) — exec-движок для построения конструкций
- [Система стилей](styles.md) — **главный** справочник по стилям, слоям и label placement
- [Гибкий импорт из GeoGebra (ImportPolicy)](import_policies.md)
- [Имена полей геометрических классов](field_names.md) — соответствия GGB XML / `ggb_raw` / `elem.style` / JSON / renderer
- [Компактный summary конструкции](construction_summary.md) — JSON-summary для AI-стилизации

## Экспорт

- [Форматы экспорта](export_formats.md) — SVG / PDF / EPS / TikZ / JSXGraph / видео
- [TikZ export](tikz_export.md) — семантический нативный TikZ для LaTeX

## Для AI-агентов

- `animageo --ai-guide` / `animageo/AI_USAGE_PROMPT.md` — самодостаточный гайд для стороннего ИИ
- [Контекст для AI-генерации стилей](ai_style_generation_context.md)
- [JSON Schema для AI style JSON](ai_style_json_schema.json)
- [Контекст для AI-создания/редактирования конструкций](ai_construction_generation_context.md)

## Интерактивный гайд

- [Гайд (HTML)](guide/index.html) — 10 глав: DSL, GeoGebra, стили, подписи, кривые, анимация, экспорт, рецепты

## Прочее

- [Особенности и подводные камни](gotchas.md)
- [Направления развития](roadmap.md)
- [../CHANGELOG.md](../CHANGELOG.md) — история релизов
