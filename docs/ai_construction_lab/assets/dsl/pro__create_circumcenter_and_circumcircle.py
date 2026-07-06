# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(1, 4)

# Sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Perpendicular bisectors
perp_bis_AB = PerpendicularBisector(A, B)
perp_bis_BC = PerpendicularBisector(B, C)

# Circumcenter
O = Intersect(perp_bis_AB, perp_bis_BC)

# Circumcircle
circumcircle = Circle(O, A)

# Radii
OA = Segment(O, A)
OB = Segment(O, B)
OC = Segment(O, C)

# Midpoints
M_AB = Midpoint(A, B)
M_BC = Midpoint(B, C)

# Right angles at midpoints
right_angle_AB = Angle(A, M_AB, O)
right_angle_BC = Angle(B, M_BC, O)

# Styling
style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(perp_bis_AB, perp_bis_BC, stroke="color.aux", stroke_width_px="line_width.aux")
style(O, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(circumcircle, stroke="color.accent", stroke_width_px="line_width.bold")
style(OA, OB, OC, stroke="color.aux", stroke_width_px="line_width.aux", tick_count=1)
style(right_angle_AB, right_angle_BC, right_angle_marker=True, right_angle_size_px="angle_radius.right")
style(M_AB, M_BC, label_visible=False, fill="color.aux", size_px="point_size.aux")
