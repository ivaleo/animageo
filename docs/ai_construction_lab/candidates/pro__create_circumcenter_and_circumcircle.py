# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)
style(A, B, C, label_visible=True)

# Sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Midpoints
M_AB = Midpoint(A, B)
M_BC = Midpoint(B, C)
M_CA = Midpoint(C, A)
style(M_AB, M_BC, M_CA, fill="color.aux", size_px="point_size.aux", label_visible=False)

# Perpendicular bisectors
perp_AB = PerpendicularBisector(A, B)
perp_BC = PerpendicularBisector(B, C)
perp_CA = PerpendicularBisector(C, A)
style(perp_AB, perp_BC, perp_CA, stroke="color.aux", stroke_width_px="line_width.aux")

# Circumcenter
O = Intersect(perp_AB, perp_BC)
style(O, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$O$")

# Circumcircle
circumcircle = Circle(O, A)
style(circumcircle, stroke="color.accent", stroke_width_px="line_width.bold")

# Right angle markers at midpoints on perpendicular bisectors
right_angle_AB = Angle(A, M_AB, O)
right_angle_BC = Angle(B, M_BC, O)
right_angle_CA = Angle(C, M_CA, O)
style(right_angle_AB, right_angle_BC, right_angle_CA, right_angle_marker=True, right_angle_size_px="angle_radius.right")
