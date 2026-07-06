# Central and inscribed angles subtending the same arc
# Circle with center O, points A, B on circle, point C on circle (distinct from A, B)
O = Point(0, 0)
A = Point(2.5, 0)
B = Rotate(A, 2 * pi / 3, O)
C = Rotate(A, 5 * pi / 6, O)
circle = Circle(O, A)

# Radii and chords
OA = Segment(O, A)
OB = Segment(O, B)
CA = Segment(C, A)
CB = Segment(C, B)

# Angles
central = Angle(A, O, B)
inscribed = Angle(A, C, B)

# Style: main geometry
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(OA, OB, CA, CB, stroke="color.main", stroke_width_px="line_width.main")
style(O, A, B, C, fill="color.main", size_px="point_size.main", label_visible=True)

# Style: angle arcs with labels
style(central, arc_size_px="angle_radius.bold", tick_count=0, label_text="$2\\alpha$", label_visible=True)
style(inscribed, arc_size_px="angle_radius.bold", tick_count=0, label_text="$\\alpha$", label_visible=True)

# Hide helper objects if any (none here)
