# Free points for triangle ABC and pedal point P
A = Point(-3, -2)
B = Point(4, -1)
C = Point(0, 3)
P = Point(1, 1)

# Triangle sides as lines for perpendicular feet
line_BC = Line(B, C)
line_CA = Line(C, A)
line_AB = Line(A, B)

# Perpendicular lines from P to each side
perp_BC = PerpendicularLine(P, line_BC)
perp_CA = PerpendicularLine(P, line_CA)
perp_AB = PerpendicularLine(P, line_AB)

# Feet of perpendiculars
D = Intersect(perp_BC, line_BC)
E = Intersect(perp_CA, line_CA)
F = Intersect(perp_AB, line_AB)

# Pedal triangle sides
DE = Segment(D, E)
EF = Segment(E, F)
FD = Segment(F, D)

# Style: triangle vertices and pedal point visible, pedal triangle highlighted
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")
style(P, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(D, E, F, label_visible=True, fill="color.aux", size_px="point_size.aux")
style(DE, EF, FD, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide construction helpers
hide(perp_BC, perp_CA, perp_AB, line_BC, line_CA, line_AB)

# Mark right angles at feet
right_D = Angle(B, D, P)
right_E = Angle(C, E, P)
right_F = Angle(A, F, P)
style(right_D, right_E, right_F, right_angle_marker=True, right_angle_size_px="angle_radius.right")
