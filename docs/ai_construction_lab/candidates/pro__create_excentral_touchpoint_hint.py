# Triangle ABC
A = Point(-3, 2)
B = Point(-1, -2)
C = Point(4, 1)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Internal angle bisector at A
bis_A = AngularBisector(B, A, C)

# External angle bisector at B
bis_B_int = AngularBisector(A, B, C)
ext_B = PerpendicularLine(B, bis_B_int)

# Excenter opposite A (intersection of internal bisector at A and external at B)
I_A = Intersect(bis_A, ext_B)
style(I_A, label_visible=True, label_text="$I_A$", fill="color.accent", size_px="point_size.bold")

# Tangency point on BC: drop perpendicular from I_A to line BC
perp_BC = PerpendicularLine(I_A, BC)
T_A = Intersect(perp_BC, BC)
style(T_A, label_visible=True, label_text="$T_A$", fill="color.accent", size_px="point_size.bold")

# Excircle (center I_A, radius I_A T_A)
excircle = Circle(I_A, T_A)
style(excircle, stroke="color.accent", stroke_width_px="line_width.bold")

# Right angle marker at tangency
right_angle = Angle(B, T_A, I_A)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide construction helpers
hide(bis_A, bis_B_int, ext_B, perp_BC)
