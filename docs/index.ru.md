# AnimaGeo — документация

**GeoGebra → Python → Manim → SVG / MP4**

AnimaGeo превращает геометрические построения GeoGebra в качественные
иллюстрации и анимации: разбирает файлы `.ggb`, строит граф зависимостей между
объектами, отрисовывает сцену через Manim и экспортирует результат в SVG
(Cairo), PDF/EPS, TikZ, интерактивный JSXGraph или видео
(MP4/GIF/WebM/PNG). Построение можно создать и напрямую во встроенном Python
DSL, без файла GeoGebra.

## С чего начать

- [Быстрый старт](quickstart.md) — установка, первый рендер, CLI и код
- [Архитектура](architecture.md) — конвейер обработки и карта модулей
- [README проекта](https://github.com/ivaleo/animageo#readme) — обзор и список возможностей

## Справочник

- [API](api.md) — методы сцены и конструкции
- [Анимация по ключевым кадрам](keyframes.md) — формат JSON/таймлайна для `play_keyframes`, стили, видимость, камера и события v2
- [Python DSL](python_dsl.md) — движок создания конструкций, выполняющий Python-код
- [Система стилей](styles.md) — **основное** описание стилей, слоёв и размещения подписей
- [Гибкий импорт GeoGebra (ImportPolicy)](import_policies.md)
- [Поля геометрических классов](field_names.md) — соответствие GGB XML / `ggb_raw` / `elem.style` / JSON / рендерера
- [Компактная сводка конструкции](construction_summary.md) — JSON-сводка для стилизации с помощью AI

## Экспорт

- [Форматы экспорта](export_formats.md) — SVG / PDF / EPS / TikZ / JSXGraph / видео
- [Экспорт TikZ](tikz_export.md) — нативный семантический TikZ для LaTeX

## Для AI-агентов

- `animageo --ai-guide` / `animageo/AI_USAGE_PROMPT.md` — самодостаточное руководство для внешнего AI
- [Контекст генерации стилей](ai_style_generation_context.md)
- [JSON Schema для стилей, созданных AI](ai_style_json_schema.json)
- [Контекст создания и редактирования конструкций](ai_construction_generation_context.md)

## Дополнительно

- [Особенности и типичные ошибки](gotchas.md)
- [Направление развития](roadmap.md)
- [История изменений](https://github.com/ivaleo/animageo/blob/main/CHANGELOG.md)
