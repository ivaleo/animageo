"""Shared constants for AnimaGeo — no external dependencies.

Z-index tiers define the visual stacking order for geometry elements.
Scale coefficients convert between JSON style units and internal rendering units.
"""

# ── Z-index tiers ──────────────────────────────────────────────────────
# Lower z_index = rendered first (behind). Higher = rendered on top.

Z_FILL = 0.01           # Polygon/sector fills (background layer)
Z_FILL_INNER = 0.001    # Inner fill for circle sectors
Z_FILL_LABEL = 0.1      # Labels on fill-level elements
Z_ANGLE = 3             # Angle arcs
Z_LINE = 4              # Lines, circles
Z_STROKE = 5            # Segments, arcs, vectors, stroke overlays
Z_POINT = 50            # Points (topmost geometry)
Z_LABEL = 50            # Labels on stroke-level elements

# ── Scale coefficients ─────────────────────────────────────────────────
# Convert between JSON style units and internal rendering units.

STYLE_TO_INTERNAL = 0.02    # JSON style unit -> internal coordinate scale
LINE_WIDTH_SCALE = 2        # JSON line width -> manim stroke width
FONT_SIZE_RATIO = 50 / 25.9 # JSON font size -> manim font size
STROKE_WIDTH_SCALE = 100    # stroke_width -> manim render units (/ ptUnit)
GGB_FONT_SCALE = 100.0      # GGB font px -> manim font_size (/ ptUnit)
