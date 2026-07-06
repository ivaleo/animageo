A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)

triangle, AB, BC, CA = Polygon(A, B, C)

incircle = Incircle(A, B, C)
I = Center(incircle)

# Touchpoints: perpendicular from I to each side
line_AB = Line(A, B)
line_BC = Line(B, C)
line_CA = Line(C, A)

perp_AB = PerpendicularLine(I, line_AB)
T_AB = Intersect(perp_AB, line_AB)

perp_BC = PerpendicularLine(I, line_BC)
T_BC = Intersect(perp_BC, line_BC)

perp_CA = PerpendicularLine(I, line_CA)
T_CA = Intersect(perp_CA, line_CA)

# Style
style(I, label_visible=True, label_text="$I$", fill="color.accent", size_px="point_size.bold")
style(T_AB, label_visible=True, label_text="$T_{AB}$", fill="color.accent", size_px="point_size.bold")
style(T_BC, label_visible=True, label_text="$T_{BC}$", fill="color.accent", size_px="point_size.bold")
style(T_CA, label_visible=True, label_text="$T_{CA}$", fill="color.accent", size_px="point_size.bold")

style(incircle, stroke="color.accent", stroke_width_px="line_width.main")

# Right angle markers at touchpoints
right_AB = Angle(T_AB, I, A)
style(right_AB, right_angle_marker=True, right_angle_size_px="angle_radius.right")
right_BC = Angle(T_BC, I, B)
style(right_BC, right_angle_marker=True, right_angle_size_px="angle_radius.right")
right_CA = Angle(T_CA, I, C)
style(right_CA, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide construction lines
hide(line_AB, line_BC, line_CA, perp_AB, perp_BC, perp_CA)

# Show incircle radius segments
r_AB = Segment(I, T_AB)
r_BC = Segment(I, T_BC)
r_CA = Segment(I, T_CA)
style(r_AB, r_BC, r_CA, stroke="color.aux", stroke_width_px="line_width.aux")
