# Central and inscribed angles subtending the same arc AB

# Circle center and two points on the circle
O = Point(0, 0)
A = Point(-2.1, 1.7)
B = Point(2.1, 1.7)
circle = Circle(O, A)

# A third point on the circle for the inscribed angle
C = Rotate(A, 2 * pi / 3, O)

# Radii for central angle
OA = Segment(O, A)
OB = Segment(O, B)

# Chords for inscribed angle
CA = Segment(C, A)
CB = Segment(C, B)

# The arc AB (upper arc)
arc_AB = CircleArc(O, B, A)

# Central angle AOB
central_angle = Angle(A, O, B)

# Inscribed angle ACB
inscribed_angle = Angle(A, C, B)

# Style the circle and arc
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(arc_AB, stroke="color.accent", stroke_width_px="line_width.bold")

# Style radii and chords
style(OA, OB, stroke="color.main", stroke_width_px="line_width.main")
style(CA, CB, stroke="color.aux", stroke_width_px="line_width.aux")

# Style angles
style(central_angle, arc_size_px="angle_radius.bold", tick_count=2)
style(inscribed_angle, arc_size_px="angle_radius.main", tick_count=1)

# Labels
style(O, label_visible=True, fill="color.main", size_px="point_size.main")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")
style(central_angle, label_text="$2\\alpha$", label_visible=True)
style(inscribed_angle, label_text="$\\alpha$", label_visible=True)
