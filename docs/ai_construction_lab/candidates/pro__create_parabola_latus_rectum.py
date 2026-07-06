# Parabola by focus and directrix with focal chord perpendicular to axis

# Given focus and directrix
F = Point(2, 0)
A = Point(-2, 0)
B = Point(-2, 2)
directrix = Line(A, B)

# Parabola
parabola = Parabola(F, directrix)

# Axis of symmetry
axis = Axes(parabola)

# Focal chord perpendicular to axis: line through F perpendicular to axis
chord_line = PerpendicularLine(F, axis)

# Intersections of chord line with parabola
P1, P2 = Intersect(chord_line, parabola)

# Focal chord segment
focal_chord = Segment(P1, P2)

# Vertex (center of parabola)
V = Center(parabola)

# Style
style(parabola, stroke="color.main", stroke_width_px="line_width.main")
style(directrix, stroke="color.aux", stroke_width_px="line_width.aux")
style(axis, stroke="color.aux", stroke_width_px="line_width.aux")
style(focal_chord, stroke="color.accent", stroke_width_px="line_width.bold")
style(F, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(V, fill="color.aux", size_px="point_size.aux", label_visible=True)
style(P1, P2, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Hide helper line
hide(chord_line)
