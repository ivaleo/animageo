# Given circle with center O and radius OA
O = Point(0, 0)
A = Point(4, 0)
circle = Circle(O, A)

# Construct chord endpoints on the circle by rotation
B = Rotate(A, 2.0, O)
C = Rotate(A, 3.5, O)
D = Rotate(A, 5.0, O)

# Draw chords AB and CD
AB = Segment(A, B)
CD = Segment(C, D)

# Intersection point E inside the circle
E = Intersect(AB, CD)

# Style the construction
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(AB, CD, stroke="color.accent", stroke_width_px="line_width.bold")
style(A, B, C, D, E, label_visible=True, fill="color.main", size_px="point_size.main")
style(E, fill="color.accent", size_px="point_size.bold")
