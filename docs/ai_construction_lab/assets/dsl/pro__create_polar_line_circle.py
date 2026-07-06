# Given circle with center O and external point P
O = Point(0, 0)
A = Point(2, 0)
circle = Circle(O, A)
P = Point(5, 2)

# Tangents from P to the circle
t1, t2 = Tangent(P, circle)
T1 = Intersect(t1, circle)
T2 = Intersect(t2, circle)

# Tangent segments
PT1 = Segment(P, T1)
PT2 = Segment(P, T2)

# Polar line of P with respect to the circle
polar = Polar(P, circle)

# Style the circle and center
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(O, fill="color.main", size_px="point_size.main", label_visible=True)

# Style the external point P
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Style tangent points and segments
style(T1, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$T_1$")
style(T2, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$T_2$")
style(PT1, PT2, stroke="color.accent", stroke_width_px="line_width.bold")

# Style the polar line
style(polar, stroke="color.accent", stroke_width_px="line_width.bold", label_visible=True, label_text="$p$")

# Hide the infinite tangent lines
hide(t1, t2)

# Mark right angles at tangent points
OT1 = Segment(O, T1)
OT2 = Segment(O, T2)
style(OT1, OT2, stroke="color.aux", stroke_width_px="line_width.aux")

right_angle1 = Angle(P, T1, O)
right_angle2 = Angle(P, T2, O)
style(right_angle1, right_angle2, right_angle_marker=True, right_angle_size_px="angle_radius.right")
