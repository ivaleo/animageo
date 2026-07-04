# Measurement Value Labels Plan

Primary plan for a later implementation pass. Do not execute this while the
current work is focused on AI construction generation.

## Goal

Make measurement output first-class in static SVG diagrams, so prompts such as
"show the area and perimeter" can produce visible values without attaching
ad-hoc static text to unrelated geometry.

## Feedback Drivers

- `Area(...)`, `Perimeter(...)`, `Length(...)`, and `Distance(...)` currently
  compute values, but an AI-generated construction can still fail the prompt if
  those values are not visible.
- `label_mode="value"` works for drawable host elements such as segments,
  angles, circles, and polygons, but aggregate measurements such as perimeter
  need a clear standalone display pattern.

## Scope

Phase 1:

- Add or document a public DSL-level way to render a `Measure` as a label at a
  chosen anchor point.
- Support static SVG export for measure labels with `label_text`,
  `label_mode`, precision, and semantic styling.
- Keep existing element value labels stable.

Phase 2:

- Support live measure labels in animations.
  - **Done (rendering perf):** element value labels (`label_mode` `value`/
    `label_value`) now animate via `ui.ValueLabel` (manim `DecimalNumber`,
    cached digit glyphs) instead of recompiling a `Tex` per frame — ~80× faster
    per label. Static export still uses `Tex`. Master switch
    `rendering.fast_value_labels` (default true). See the "Fast Value Labels"
    section in `docs/architecture.md` and `labels.resolve_label_spec`. Standalone `Measure`
    labels, once drawable, inherit the same fast path automatically.
- Add automatic placement for standalone measurement labels.
- Add regression examples to `docs/ai_construction_lab`.

## Acceptance Cases

- A triangle area prompt shows a visible area value on or near the triangle.
- A triangle perimeter prompt shows a visible perimeter value without
  repurposing an arbitrary side label.
- A segment length prompt shows a visible value using the segment's own label.
- Precision and stripping zeros follow existing label style settings.

## Candidate Implementation Areas

- `animageo/geo/lib_vars.py`: measure display metadata if needed.
- `animageo/labels.py`: measure label text formatting is already partially
  available through `label_value_of`.
- `animageo/animageo.py`: rendering path for standalone measure labels.
- `animageo/parsers/dsl/namespace.py`: public DSL helper if a new command is
  added.
- `docs/ai_construction_lab`: add regression cases after implementation.
