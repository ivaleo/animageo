# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True)

# Circumcircle of ABC
perp_bis_AB = PerpendicularBisector(A, B)
perp_bis_BC = PerpendicularBisector(B, C)
O = Intersect(perp_bis_AB, perp_bis_BC)
circumcircle = Circle(O, A)
style(circumcircle, stroke="color.aux", stroke_width_px="line_width.aux")
hide(perp_bis_AB, perp_bis_BC)

# Point P on circumcircle (choose a point on the circle)
P = Rotate(A, 2.2, O)  # arbitrary angle to place P on the circle
style(P, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Simson line: feet of perpendiculars from P to the sides (or their extensions)
# Side AB (line through A and B)
line_AB = Line(A, B)
foot_AB = Intersect(PerpendicularLine(P, line_AB), line_AB)

# Side BC
line_BC = Line(B, C)
foot_BC = Intersect(PerpendicularLine(P, line_BC), line_BC)

# Side CA
line_CA = Line(C, A)
foot_CA = Intersect(PerpendicularLine(P, line_CA), line_CA)

# Hide infinite lines used for construction
hide(line_AB, line_BC, line_CA)

# Draw the Simson line through two of the feet
simson = Line(foot_AB, foot_BC)
style(simson, stroke="color.accent", stroke_width_px="line_width.bold")

# Mark right angles at feet (optional but helpful)
right_AB = Angle(A, foot_AB, P)
right_BC = Angle(B, foot_BC, P)
right_CA = Angle(C, foot_CA, P)
style(right_AB, right_BC, right_CA, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Show feet as points
style(foot_AB, foot_BC, foot_CA, fill="color.accent", size_px="point_size.bold", label_visible=False)

# Optionally draw perpendicular segments from P to feet (dashed)
perp_AB = Segment(P, foot_AB)
perp_BC = Segment(P, foot_BC)
perp_CA = Segment(P, foot_CA)
style(perp_AB, perp_BC, perp_CA, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")
