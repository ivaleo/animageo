# Given circle and external point
O = Point(0, 0)
A = Point(2, 0)
circle = Circle(O, A)
P = Point(4, 3)

# Tangents from P to the circle
t1, t2 = Tangent(P, circle)

# Points of tangency
T1 = Intersect(t1, circle)
T2 = Intersect(t2, circle)

# Polar line (chord of contact)
polar = Line(T1, T2)

# Tangent segments
PT1 = Segment(P, T1)
PT2 = Segment(P, T2)

# Radii to tangency points
OT1 = Segment(O, T1)
OT2 = Segment(O, T2)

# Right angle markers at tangency points
right1 = Angle(P, T1, O)
right2 = Angle(P, T2, O)

# Styling
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(O, fill="color.main", size_px="point_size.main", label_visible=True)
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(T1, T2, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text=["$T_1$", "$T_2$"])
style(PT1, PT2, stroke="color.accent", stroke_width_px="line_width.bold")
style(OT1, OT2, stroke="color.aux", stroke_width_px="line_width.aux")
style(polar, stroke="color.accent", stroke_width_px="line_width.bold", stroke_dasharray="5,5")
style(right1, right2, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(t1, t2)
