# Triangle with base AB and altitude CH
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 3)

AB = Segment(A, B)
AC = Segment(A, C)
BC = Segment(B, C)

# Altitude from C to line AB
line_AB = Line(A, B)
alt_line = PerpendicularLine(C, line_AB)
H = Intersect(alt_line, line_AB)
CH = Segment(C, H)

# Right angle marker at H
right_angle = Angle(A, H, C)

# Style: base and altitude highlighted
style(AB, stroke="color.accent", stroke_width_px="line_width.bold")
style(CH, stroke="color.accent", stroke_width_px="line_width.bold")
style(AC, BC, stroke="color.main", stroke_width_px="line_width.main")
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide construction helpers
hide(line_AB, alt_line)

# Labels
style(A, B, C, H, label_visible=True)
style(CH, label_text="h")
style(AB, label_text="b")
