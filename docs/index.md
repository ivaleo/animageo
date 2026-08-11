# AnimaGeo — Documentation

**GeoGebra → Python → Manim → SVG / MP4**

AnimaGeo turns GeoGebra geometric constructions into high-quality images and
animations: it parses `.ggb` files, builds a dependency graph between
elements, renders through manim, and exports to SVG (Cairo), PDF/EPS, TikZ,
interactive JSXGraph, or video (MP4/GIF/WebM/PNG). Constructions can also be
built directly in the embedded Python DSL, without a GeoGebra file.

## Getting started

- [Quickstart](quickstart.md) — installation, first render, CLI and code
- [Architecture](architecture.md) — pipeline and module map
- [Project README](https://github.com/ivaleo/animageo#readme) — overview and feature list

## Reference

- [API reference](api.md) — scene and construction methods
- [Keyframe animation](keyframes.md) — JSON/timeline format for `play_keyframes`, v2 styles/visibility/camera/events
- [Python DSL](python_dsl.md) — exec-based engine for building constructions
- [Style system](styles.md) — the **primary** reference for styles, layers, and label placement
- [Flexible GeoGebra import (ImportPolicy)](import_policies.md)
- [Field names of the geometric classes](field_names.md) — mapping between GGB XML / `ggb_raw` / `elem.style` / JSON / renderer
- [Compact construction summary](construction_summary.md) — JSON summary for AI-driven styling

## Export

- [Export formats](export_formats.md) — SVG / PDF / EPS / TikZ / JSXGraph / video
- [TikZ export](tikz_export.md) — semantic native TikZ for LaTeX

## For AI agents

- `animageo --ai-guide` / `animageo/AI_USAGE_PROMPT.md` — self-sufficient guide for an external AI
- [Context for AI style generation](ai_style_generation_context.md)
- [JSON Schema for AI style JSON](ai_style_json_schema.json)
- [Context for AI construction creation/editing](ai_construction_generation_context.md)

## Miscellaneous

- [Gotchas and pitfalls](gotchas.md)
- [Direction](roadmap.md)
- [Changelog](https://github.com/ivaleo/animageo/blob/main/CHANGELOG.md) — release history
