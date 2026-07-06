# Free points
A = Point(-3, 1)
B = Point(1, -2)
C = Point(2, 3)
O = Point(0, 0)

# Original triangle
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")
style(O, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Homothety factor
k = 1.6

# Image points via dependent point arithmetic: P' = O + k*(P - O)
A1 = Point(O.x + k * (A.x - O.x), O.y + k * (A.y - O.y))
B1 = Point(O.x + k * (B.x - O.x), O.y + k * (B.y - O.y))
C1 = Point(O.x + k * (C.x - O.x), O.y + k * (C.y - O.y))

# Image triangle
A1B1 = Segment(A1, B1)
B1C1 = Segment(B1, C1)
C1A1 = Segment(C1, A1)
style(A1B1, B1C1, C1A1, stroke="color.accent", stroke_width_px="line_width.bold")
style(A1, B1, C1, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Rays from center to show correspondence (auxiliary)
OA = Ray(O, A)
OB = Ray(O, B)
OC = Ray(O, C)
style(OA, OB, OC, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")

# Labels for image points
style(A1, label_text="$A'$")
style(B1, label_text="$B'$")
style(C1, label_text="$C'$")
