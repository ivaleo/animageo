# docs/archive

Historical design documents preserved for provenance: implementation **plans**,
**audits**, **research**, review **feedback rounds**, and **TZ** (technical
specification) notes for features that have since **shipped**. Their outcomes
now live in the code, the current reference docs, and `CHANGELOG.md`.

Kept here (rather than deleted) because source comments, tests, and changelog
entries cite them as the rationale for specific decisions. For current
documentation start at [`../index.md`](../index.md).

## Contents

**Export**
- `export_formats_plan.md` — plan behind [`../export_formats.md`](../export_formats.md)
- `tikz_export_plan.md` — plan behind [`../tikz_export.md`](../tikz_export.md)
- `jsxgraph_export_plan.md`, `jsxgraph_web_integration_plan.md`,
  `jsxgraph_web_integration_audit.md`, `jsxgraph/` (spike) — JSXGraph export & web runtime
- `animageo_library_export_canvas_plan.md`, `animageo_web_export_canvas_plan.md` — reference→content→export canvas model

**Label placement**
- `label_placement_research.md`, `label_placement_improvement_plan.md`,
  `label_placement_leader_lines_plan.md`, `label_autoplacement_plan.md`,
  `label_placement_feedback_round1.md`, `label_placement_tz_round19.md`,
  `label_placement_examples/` — the automatic label-placement effort

**Other features / fixes**
- `dsl_intersect_index_keyword_plan.md` — indexed intersection keyword
- `measurement_value_labels_plan.md` — DecimalNumber-backed value labels
- `fix-rendered-bounds-label-clipping.md` — rendered-bounds re-fit
- `TZ-conic-line-intersection-index-order.md`,
  `TZ-conic-locus-point-keyframe-animation.md`,
  `TZ-label-placement-angle-markers.md`,
  `TZ-mathtex-set-default-recursion-leak.md` — shipped TZ specs
- `superpowers/` — plan/spec artifacts for the above fixes

**Audits**
- `geogebra_command_audit.md` — point-in-time GeoGebra command coverage
- `guide_audit.md`, `guide_rework_plan.md` — the [HTML guide](../guide/) rework
