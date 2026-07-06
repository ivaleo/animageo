# Free points for the triangle and center of rotation
A = Point(2, 3)
B = Point(5, 1)
C = Point(3, 6)
O = Point(0, 0)

# Original triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")
style(O, label_visible=True, fill="color.aux", size_px="point_size.aux")

# Rotated triangle vertices
A1 = Rotate(A, pi/3, O)
B1 = Rotate(B, pi/3, O)
C1 = Rotate(C, pi/3, O)

# Rotated triangle sides
A1B1 = Segment(A1, B1)
B1C1 = Segment(B1, C1)
C1A1 = Segment(C1, A1)
style(A1B1, B1C1, C1A1, stroke="color.accent", stroke_width_px="line_width.bold")
style(A1, B1, C1, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Optional: show rotation arcs for clarity
arc_A = CircleArc(O, A, A1)
arc_B = CircleArc(O, B, B1)
arc_C = CircleArc(O, C, C1)
style(arc_A, arc_B, arc_C, stroke="color.aux", stroke_width_px="line_width.aux")
