# AI Style Generation Test: Scene 10

This folder is a small reproducible fixture for testing LLM-generated
AnimaGeo styles.

Files:

- `scene10.ggb` — copied source GeoGebra construction.
- `style.json` — current style JSON used as the base or as a target to
  replace with AI-generated JSON.
- `ai_style.dsl.py` — optional AnimaGeo Python DSL style overrides. Replace
  this with the `PYTHON_DSL` section returned by the AI when needed.
- `run_scene.py` — loads the `.ggb`, applies `style.json`, exports
  `summary.json` for AI, loads `ai_style.dsl.py`, and exports `scene10.svg`
  for visual review.

Run from the repo root:

```bash
python examples/ai_style_generation_scene10/run_scene.py
```

The command requires the normal AnimaGeo rendering environment with `manim`
installed.

Generated files stay in this folder:

- `summary.json`
- `scene10.svg`
- `scene10_stubs.pyi`
