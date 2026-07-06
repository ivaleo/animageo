# Given circle with center O and external point P
O = Point(0, 0)
A = Point(2, 0)
circle = Circle(O, A)
P = Point(5, 2)

# Construct tangents from P to the circle
t1, t2 = Tangent(P, circle)

# Find tangent points
T1 = Intersect(t1, circle)
T2 = Intersect(t2, circle)

# Draw tangent segments
PT1 = Segment(P, T1)
PT2 = Segment(P, T2)

# Draw radii to tangent points
OT1 = Segment(O, T1)
OT2 = Segment(O, T2)

# Mark right angles at tangent points
right1 = Angle(P, T1, O)
right2 = Angle(P, T2, O)

# Mark equal tangent segments
style(PT1, PT2, stroke="color.accent", stroke_width_px="line_width.bold", tick_count=1)

# Style radii and right angles
style(OT1, OT2, stroke="color.aux", stroke_width_px="line_width.aux")
style(right1, right2, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide infinite tangent lines
hide(t1, t2)

# Style points
style(O, fill="color.main", size_px="point_size.main", label_visible=True)
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(T1, T2, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Style circle
style(circle, stroke="color.main", stroke_width_px="line_width.main")
