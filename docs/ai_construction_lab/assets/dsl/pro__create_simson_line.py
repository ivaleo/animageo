# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Circumcircle of ABC
perp_bis_AB = PerpendicularBisector(A, B)
perp_bis_BC = PerpendicularBisector(B, C)
O = Intersect(perp_bis_AB, perp_bis_BC)
circumcircle = Circle(O, A)
style(circumcircle, stroke="color.aux", stroke_width_px="line_width.aux")
hide(perp_bis_AB, perp_bis_BC)

# Point P on circumcircle (choose a generic point by rotating A around O)
P = Rotate(A, 2.0, O)
style(P, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Simson line: feet of perpendiculars from P to the three side lines
# Side lines (infinite lines through triangle sides)
line_AB = Line(A, B)
line_BC = Line(B, C)
line_CA = Line(C, A)

# Perpendicular lines from P to each side line
perp_AB = PerpendicularLine(P, line_AB)
perp_BC = PerpendicularLine(P, line_BC)
perp_CA = PerpendicularLine(P, line_CA)

# Feet (intersections of perpendiculars with side lines)
foot_AB = Intersect(perp_AB, line_AB)
foot_BC = Intersect(perp_BC, line_BC)
foot_CA = Intersect(perp_CA, line_CA)

# Hide helper lines
hide(line_AB, line_BC, line_CA, perp_AB, perp_BC, perp_CA)

# Draw the Simson line through two of the feet
simson_line = Line(foot_AB, foot_BC)
style(simson_line, stroke="color.accent", stroke_width_px="line_width.bold")

# Mark right angles at feet (optional but clarifies perpendicularity)
right_angle_AB = Angle(A, foot_AB, P)
right_angle_BC = Angle(B, foot_BC, P)
right_angle_CA = Angle(C, foot_CA, P)
style(right_angle_AB, right_angle_BC, right_angle_CA, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Style feet
style(foot_AB, foot_BC, foot_CA, fill="color.accent", size_px="point_size.bold", label_visible=False)
