# Showcase

Small self-contained examples, each a single script with its rendered output
committed next to it.

| Example | What it shows |
|---------|---------------|
| [`conics_and_functions.py`](conics_and_functions.py) → [`conics_and_functions.svg`](conics_and_functions.svg) | Pure-DSL scene (no `.ggb`): a conic from an equation, a function graph, an implicit lemniscate, cross-type `Intersect`, `Center`/`Focus`, packaged `default` style, `fitView` + `autoPlaceLabels` |

Run any example with the library importable (e.g. `pip install animageo`, or
`PYTHONPATH=../..` from this directory):

```bash
python conics_and_functions.py
```

See also:

- [`../policies/`](../policies/) — ready-made `ImportPolicy` JSON presets
- [`../ai_style_generation_scene10/`](../ai_style_generation_scene10/) — an
  end-to-end AI style-generation session (GGB + summary + generated style)
- The README hero animation: [`../../docs/readme_assets/`](../../docs/readme_assets/)
  (rendered from a `.ggb` with a committed keyframe timeline)
