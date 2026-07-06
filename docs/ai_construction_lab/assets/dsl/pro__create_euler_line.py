# Triangle ABC
A = Point(-3, -1)
B = Point(4, -2)
C = Point(0, 5)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Centroid G
G = Centroid(A, B, C)
style(G, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Orthocenter H
alt_B = PerpendicularLine(B, CA)
alt_C = PerpendicularLine(C, AB)
H = Intersect(alt_B, alt_C)
style(H, label_visible=True, fill="color.accent", size_px="point_size.bold")
hide(alt_B, alt_C)

# Circumcenter O
perp_bis_AB = PerpendicularBisector(A, B)
perp_bis_BC = PerpendicularBisector(B, C)
O = Intersect(perp_bis_AB, perp_bis_BC)
style(O, label_visible=True, fill="color.accent", size_px="point_size.bold")
hide(perp_bis_AB, perp_bis_BC)

# Euler line
euler = Line(O, G)
style(euler, stroke="color.accent", stroke_width_px="line_width.bold")

# Verify H lies on Euler line (optional, for correctness)
# H is already on the line by construction, but we can mark it
style(H, fill="color.accent", size_px="point_size.bold")
