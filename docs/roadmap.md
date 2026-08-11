# Direction

Open, forward-looking work. Shipped work lives in the
[changelog](https://github.com/ivaleo/animageo/blob/main/CHANGELOG.md).

## Rendering & export

- **Programmatic single-call render API.** Today MP4/GIF rendering goes through
  the manim CLI. A `render(ggb_path, style=..., output_format=..., size=...)`
  entry point would make animageo embeddable in servers and pipelines without
  shelling out.
- **In-memory input.** Accept `bytes`/`BytesIO` for `.ggb` and style JSON in
  addition to file paths.
- **Snapshot tests for rendering.** The geometry core is well covered
  (~985 tests); `CreateMObject`, SVG output, and the CLI still rely on manual
  inspection. Golden-file snapshot tests would lock the visual output down.

## GeoGebra coverage

Most everyday commands are implemented (433 dispatch signatures exposed
through 99 auto-discovered DSL factories). Known gaps:

- Exact/symbolic `Locus` and `LocusEquation` (current `Locus` is a sampled
  polyline).
- `RadicalAxis`, `Power` (circle power-of-a-point family).
- Exact `Circumference` for ellipses (currently Ramanujan's approximation).
- `OsculatingCircle`, `Curvature`, `ConjugateDiameter`, `PathParameter`.
- Element types `boolean` (as a visible checkbox), `list`, `image`.

## Label placement

Automatic placement has reached its target quality for solver-only layouts
(see the recommended preset in [`styles.md`](styles.md)). Remaining ideas:

- Leader-line refinement for dense scenes (suppressing unhelpful connectors).
- Soft repulsion between labels across keyframes to avoid transient overlaps
  mid-animation.

## Keyframes

- `passing_flash` emphasis event.
- Pixel-invariant camera zoom (GeoGebra-style `ZoomIn` semantics: geometry
  scales, pixel-sized decorations do not) — the current `@camera` track is
  cinematic (everything scales together).

## API ergonomics

- Chainable style helpers (`element('s').setDashed(0.65).setOpacity(0.5)`)
  as sugar over `elem.style[...]` writes.

## Distribution

- Publish the JSXGraph web runtime (`web/runtime`, `web/web-component`) to npm.

Suggestions and contributions are welcome — see
[CONTRIBUTING.md](https://github.com/ivaleo/animageo/blob/main/CONTRIBUTING.md).
