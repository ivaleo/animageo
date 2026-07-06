A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
tri, AB, BC, CA = Polygon(A, B, C)

# Centroid
G = Centroid(tri)

# Orthocenter
alt_A = PerpendicularLine(A, BC)
H_A = Intersect(alt_A, BC)
alt_B = PerpendicularLine(B, CA)
H_B = Intersect(alt_B, CA)
H = Intersect(alt_A, alt_B)
hide(alt_A, alt_B)

# Circumcenter
bis_AB = LineBisector(A, B)
bis_BC = LineBisector(B, C)
O = Intersect(bis_AB, bis_BC)
hide(bis_AB, bis_BC)

# Euler line
euler = Line(O, H)

# Style
style(A, B, C, label_visible=True)
style(G, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(H, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(O, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(euler, stroke="color.accent", stroke_width_px="line_width.bold")
style(tri, fill="color.aux", opacity=0.1)
