# Free points for triangle ABC and point P
A = Point(-4, -2)
B = Point(4, -2)
C = Point(0, 4)
P = Point(1, 1)

# Triangle sides as lines (needed for perpendicular feet)
line_AB = Line(A, B)
line_BC = Line(B, C)
line_CA = Line(C, A)

# Perpendiculars from P to each side line
perp_AB = PerpendicularLine(P, line_AB)
perp_BC = PerpendicularLine(P, line_BC)
perp_CA = PerpendicularLine(P, line_CA)

# Feet of the perpendiculars (pedal points)
D = Intersect(perp_AB, line_AB)
E = Intersect(perp_BC, line_BC)
F = Intersect(perp_CA, line_CA)

# Pedal triangle sides
DE = Segment(D, E)
EF = Segment(E, F)
FD = Segment(F, D)

# Right angle markers at the feet
right_D = Angle(A, D, P)
right_E = Angle(B, E, P)
right_F = Angle(C, F, P)

# Styling
style(A, B, C, P, label_visible=True)
style(D, E, F, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(DE, EF, FD, stroke="color.accent", stroke_width_px="line_width.bold")
style(right_D, right_E, right_F, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide construction helpers
hide(line_AB, line_BC, line_CA, perp_AB, perp_BC, perp_CA)

# Show original triangle with main style
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
