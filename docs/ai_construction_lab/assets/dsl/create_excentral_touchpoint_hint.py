A = Point(0, 3)
B = Point(-4, 0)
C = Point(2, 0)
tri, AB, BC, CA = Polygon(A, B, C)

# Angle bisectors for excenter opposite A
bis_A = AngularBisector(B, A, C)
bis_B = AngularBisector(A, B, C)
ext_B = PerpendicularLine(B, bis_B)
I_A = Intersect(bis_A, ext_B)

# Tangency point on BC
line_BC = Line(B, C)
perp_IA = PerpendicularLine(I_A, line_BC)
T = Intersect(perp_IA, line_BC)

# Excircle and right angle
excircle = Circle(I_A, T)
right_angle = Angle(B, T, I_A)

# Hide auxiliary lines
hide(bis_A, bis_B, ext_B, line_BC, perp_IA)

# Style for visibility
style(A, B, C, label_visible=True)
style(tri, stroke="color.strong", stroke_width_px="line_width.bold")
style(excircle, stroke="color.accent", stroke_width_px="line_width.bold")
style(T, label_visible=True, label_text="$T$", fill="color.accent", size_px="point_size.bold")
style(I_A, label_visible=True, label_text="$I_A$", size_px="point_size.aux", fill="color.aux")
style(right_angle, right_angle_marker=True)
