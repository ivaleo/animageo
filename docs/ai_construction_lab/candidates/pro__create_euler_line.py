# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(1, 4)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Centroid G
M_AB = Midpoint(A, B)
M_BC = Midpoint(B, C)
median_A = Line(A, M_BC)
median_B = Line(B, M_AB)
G = Intersect(median_A, median_B)

# Orthocenter H
alt_A = PerpendicularLine(A, BC)
alt_B = PerpendicularLine(B, CA)
H = Intersect(alt_A, alt_B)

# Circumcenter O
perp_bis_AB = PerpendicularBisector(A, B)
perp_bis_BC = PerpendicularBisector(B, C)
O = Intersect(perp_bis_AB, perp_bis_BC)

# Euler line
euler = Line(O, H)

# Styling
style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(G, H, O, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(euler, stroke="color.accent", stroke_width_px="line_width.bold")
hide(median_A, median_B, alt_A, alt_B, perp_bis_AB, perp_bis_BC, M_AB, M_BC)
