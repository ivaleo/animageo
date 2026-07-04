# Label Autoplacement Plan

Primary plan for a later implementation pass. Do not execute this while the
current work is focused on AI construction generation.

## Goal

Improve `scene.autoPlaceLabels()` so labels avoid more geometry classes and can
place labels for infinite or extended objects in a predictable way.

## Feedback Drivers

- Names like `F_ab` should render as `$F_{ab}$`, not `$F_ab$`.
  This intentionally favors diagram-label convention over literal TeX
  compilation of the Python identifier: the code name `F_ab` should map to the
  expected drawing label with the full `ab` suffix as one subscript group.
- Abstract named lines such as `l` need visible labels even when their defining
  helper points are hidden.
- Infinite-object labels should have lower placement priority than labels for
  points, angles, and finite segments.
- Label placement should avoid visible straight geometry: lines, rays,
  segments, vectors, and polygon boundaries.
- Conics should be considered if feasible. Functions and arbitrary implicit
  curves are lower priority because collision sampling is more complex.

## Scope

Phase 1:

- Add canonical label text formatting for names with underscores:
  - `F1` -> `$F_1$` when auto-math labeling is active;
  - `F_ab` -> `$F_{ab}$`;
  - keep explicit `label_text` as the highest priority.
- Add candidate anchor generation for `Line`, `Ray`, and `Vector`.
- Penalize candidates that collide with straight geometry.
- Keep existing point, segment, and angle behavior stable.

Phase 2:

- Add conic-aware penalties for circles, ellipses, hyperbolas, and parabolas.
- Add label candidates for `Circle`, `Conic`, `Function`, and
  `ImplicitCurve` where reliable.
- Add viewport clipping awareness for infinite line labels.

## Placement Priorities

From highest to lowest:

1. Explicit `label_offset_px` and `label_anchor`.
2. Point labels.
3. Angle labels.
4. Segment/vector/ray labels.
5. Line labels.
6. Circle/conic labels.
7. Function/implicit labels.

## Acceptance Cases

- A line named `l` appears as `$l$` inside the viewport without showing helper
  points used only to define it.
- A triangle with side foot labels `F_ab`, `F_bc`, `F_ca` renders labels as
  `$F_{ab}$`, `$F_{bc}$`, `$F_{ca}$`.
- Labels avoid crossing the sides of a dense triangle with medians, altitudes,
  and perpendicular bisectors.
- A circumcircle label, when enabled, is placed near the circle and does not
  overlap key points.

## Candidate Implementation Areas

- `animageo/labels.py`: label text canonicalization.
- `animageo/label_placement.py`: candidate generation and collision scoring.
- `animageo/animageo.py`: `autoPlaceLabels()` integration and priority order.
- `docs/ai_construction_lab`: add regression cases after implementation.
