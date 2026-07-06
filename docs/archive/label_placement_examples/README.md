# Label-placement comparison & feedback tool

Interactive before/after viewer for the automatic label-placement mechanism,
with built-in feedback capture. Used to drive **principle-level** improvements
(see [`../label_placement_improvement_plan.md`](../label_placement_improvement_plan.md)).

## Generate / refresh the page

```bash
# from the repo root (so the local animageo package is importable)
PYTHONPATH=. python3.13 docs/archive/label_placement_examples/build_feedback_compare.py
```

Renders ~22 `examples/*.ggb` in three variants and writes `compare.html`
(self-contained, inline SVG). The HTML and `_tmp.svg` are **gitignored** (large,
embed untracked example renders); only `build_feedback_compare.py` and this
README are tracked.

Variants per drawing:

| Column | Settings |
|--------|----------|
| **Original** | GGB as authored — no auto-placement |
| **Auto** | current greedy solver (`label_placement.enabled`) |
| **Auto + P0** | `repair_iterations:6, soft_falloff_px:8, respect_current_position:true` + `rendering.label_contrast:auto` |

## Give feedback

```bash
open docs/archive/label_placement_examples/compare.html
```

For each example, under each drawing leave a **rating** (👍 / 🟡 / 👎) and a
**comment** — *what works, what doesn't, and why; how it should look ideally*.
Use the per-example "Общий вывод" box for the principle, not the one-off fix.
Everything auto-saves to `localStorage`.

Click **⬇ Экспорт JSON** to download `label_placement_feedback_round{N}.json`
(`⬇ Экспорт MD` for a readable summary), where `{N}` is the `ROUND` set in the
generator. Each round uses its own `localStorage` key, so bumping `ROUND` starts
the page with an empty slate (previous round's comments are not loaded).

## Hand the feedback back to the agent

Give the agent the exported `label_placement_feedback.json` and ask it to
process it. The agent will:

1. read each comment against its drawing,
2. cluster the feedback into **general criteria/principles** (not per-case
   patches),
3. map those to concrete, configurable improvements in the placement mechanism
   (`animageo/label_placement.py` cost terms / candidate generation / passes,
   and `rendering.*` for legibility),
4. update the improvement plan and implement, behind flags, with tests.

### Feedback JSON shape

```json
{
  "generated_by": "animageo label feedback tool",
  "variants": { "orig": "...", "auto": "...", "p0": "..." },
  "feedback": {
    "ex0": {
      "label": "folder / scene",
      "variants": {
        "orig": { "rating": "bad", "comment": "..." },
        "auto": { "rating": "ok",  "comment": "..." },
        "p0":   { "rating": "good","comment": "..." }
      },
      "overall": "principle, not a one-off fix"
    }
  }
}
```
