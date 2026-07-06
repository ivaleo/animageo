# Parabola by focus and directrix with focal chord perpendicular to axis

# Given focus and directrix
F = Point(2, 0)
style(F, label_visible=True, label_text="$F$", fill="color.accent", size_px="point_size.bold")

# Directrix: vertical line x = -2
D1 = Point(-2, -3)
D2 = Point(-2, 3)
directrix = Line(D1, D2)
style(directrix, stroke="color.aux", stroke_width_px="line_width.aux", label_visible=True, label_text="$d$")
hide(D1, D2)

# Parabola
parabola = Parabola(F, directrix)
style(parabola, stroke="color.main", stroke_width_px="line_width.main")

# Axis of symmetry
axis = Axes(parabola)
style(axis, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")

# Vertex
V = Center(parabola)
style(V, label_visible=True, label_text="$V$", fill="color.main", size_px="point_size.main")

# Focal chord perpendicular to axis
# Intersect parabola with line through F perpendicular to axis
perp_line = PerpendicularLine(F, axis)
P1, P2 = Intersect(parabola, perp_line)

# Draw focal chord
chord = Segment(P1, P2)
style(chord, stroke="color.accent", stroke_width_px="line_width.bold")
style(P1, label_visible=True, label_text="$P_1$", fill="color.accent", size_px="point_size.bold")
style(P2, label_visible=True, label_text="$P_2$", fill="color.accent", size_px="point_size.bold")

# Right angle marker at F between axis and chord
right_angle = Angle(P1, F, V)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide helper perpendicular line
hide(perp_line)
