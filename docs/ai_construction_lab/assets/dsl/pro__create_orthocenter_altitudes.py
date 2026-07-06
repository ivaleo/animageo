# Triangle ABC
A = Point(-3, -2)
B = Point(4, -1)
C = Point(0, 4)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Altitude from A to BC
line_BC = Line(B, C)
alt_A_line = PerpendicularLine(A, line_BC)
D = Intersect(alt_A_line, line_BC)
AD = Segment(A, D)
style(AD, stroke="color.accent", stroke_width_px="line_width.bold")
right_angle_D = Angle(B, D, A)
style(right_angle_D, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(line_BC, alt_A_line)

# Altitude from B to CA
line_CA = Line(C, A)
alt_B_line = PerpendicularLine(B, line_CA)
E = Intersect(alt_B_line, line_CA)
BE = Segment(B, E)
style(BE, stroke="color.accent", stroke_width_px="line_width.bold")
right_angle_E = Angle(C, E, B)
style(right_angle_E, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(line_CA, alt_B_line)

# Altitude from C to AB
line_AB = Line(A, B)
alt_C_line = PerpendicularLine(C, line_AB)
F = Intersect(alt_C_line, line_AB)
CF = Segment(C, F)
style(CF, stroke="color.accent", stroke_width_px="line_width.bold")
right_angle_F = Angle(A, F, C)
style(right_angle_F, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(line_AB, alt_C_line)

# Orthocenter H (intersection of two altitudes)
H = Intersect(AD, BE)
style(H, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Hide feet labels unless needed
style(D, E, F, label_visible=False, size_px="point_size.aux")
