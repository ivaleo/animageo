A = Point(-3, -1)
B = Point(4, -1)
C = Point(1, 3)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Perpendicular bisectors
M_AB = Midpoint(A, B)
M_BC = Midpoint(B, C)
M_CA = Midpoint(C, A)

perp_AB = PerpendicularLine(M_AB, AB)
perp_BC = PerpendicularLine(M_BC, BC)
perp_CA = PerpendicularLine(M_CA, CA)

# Circumcenter
O = Intersect(perp_AB, perp_BC)

# Circumcircle
circ = Circle(O, A)

# Right angle markers for perpendicular bisectors
# For perp_AB: right angle at M_AB between AB and perp_AB
# Use a point on perp_AB to define angle
# Choose a point on perp_AB distinct from M_AB
# We can use the intersection of perp_AB with a line through M_AB parallel to something, but simpler: use a point on perp_AB via rotation
# Instead, create a helper point on perp_AB by rotating A around M_AB by 90 degrees? Not needed: we can use the fact that perp_AB is perpendicular to AB, so angle between AB and perp_AB at M_AB is right.
# Define angle with vertex M_AB, arms along AB and perp_AB. Need a point on perp_AB other than M_AB. Use O (circumcenter) which lies on perp_AB.
right1 = Angle(A, M_AB, O)
style(right1, right_angle_marker=True, right_angle_size_px="angle_radius.right")

right2 = Angle(B, M_BC, O)
style(right2, right_angle_marker=True, right_angle_size_px="angle_radius.right")

right3 = Angle(C, M_CA, O)
style(right3, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Style
style(A, B, C, label_visible=True)
style(O, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(circ, stroke="color.accent", stroke_width_px="line_width.bold")
style(perp_AB, perp_BC, perp_CA, stroke="color.aux", stroke_width_px="line_width.aux")
style(M_AB, M_BC, M_CA, label_visible=False, size_px="point_size.aux")
