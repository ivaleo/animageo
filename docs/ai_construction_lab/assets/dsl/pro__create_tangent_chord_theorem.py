O = Point(0, 0)
A = Point(1.5, 2.0)
circle = Circle(O, A)
B = Rotate(A, 2.0, O)
chord = Segment(A, B)

# Tangent at A: helper point T_dir on tangent line
T_dir = Rotate(O, pi / 2, A)
tangent_line = Line(A, T_dir)

# Point C on the circle, not coincident with A or B
C = Rotate(A, 4.0, O)

# Inscribed angle ACB
angle_ACB = Angle(A, C, B)

# Angle between chord AB and tangent at A: angle between AB and tangent_line
# Use a point on the tangent line distinct from A to define the angle
angle_chord_tangent = Angle(B, A, T_dir)

# Style primary objects
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(chord, stroke="color.main", stroke_width_px="line_width.bold")
style(A, B, C, fill="color.main", size_px="point_size.main", label_visible=True)
style(O, fill="color.aux", size_px="point_size.aux", label_visible=False)

# Style tangent line as auxiliary, but keep visible
style(tangent_line, stroke="color.aux", stroke_width_px="line_width.aux")

# Style angles
style(angle_ACB, arc_size_px="angle_radius.main", tick_count=1)
style(angle_chord_tangent, arc_size_px="angle_radius.main", tick_count=1)

# Hide helper point T_dir
hide(T_dir)
