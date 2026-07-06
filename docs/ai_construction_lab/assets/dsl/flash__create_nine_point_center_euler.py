A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
tri, AB, BC, CA = Polygon(A, B, C)

# Altitudes and orthocenter H
alt_A = PerpendicularLine(A, BC)
alt_B = PerpendicularLine(B, CA)
H = Intersect(alt_A, alt_B)

# Perpendicular bisectors and circumcenter O
mid_AB = Midpoint(A, B)
mid_BC = Midpoint(B, C)
pb_AB = PerpendicularLine(mid_AB, AB)
pb_BC = PerpendicularLine(mid_BC, BC)
O = Intersect(pb_AB, pb_BC)

# Nine-point circle center N (midpoint of OH)
N = Midpoint(O, H)

# Euler line through O, N, H
euler_line = Line(O, H)

# Style: hide helpers, show result points and line
hide(alt_A, alt_B, pb_AB, pb_BC, mid_AB, mid_BC)
style(H, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(O, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(N, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(euler_line, stroke="color.accent", stroke_width_px="line_width.bold")
style(A, B, C, label_visible=True)
style(tri, fill="color.aux", stroke="color.main", stroke_width_px="line_width.main")
