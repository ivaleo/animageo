A = Point(-2, 0)
B = Point(2, 0)
AB = Segment(A, B)
style(AB, stroke="color.main", stroke_width_px="line_width.main")

# Equal compass circles
circle_A = Circle(A, B)
circle_B = Circle(B, A)
style(circle_A, circle_B, stroke="color.aux", stroke_width_px="line_width.aux")

# Intersection points of the two circles
P, Q = Intersect(circle_A, circle_B)

# Perpendicular bisector line through P and Q
perp_bisector = Line(P, Q)
style(perp_bisector, stroke="color.accent", stroke_width_px="line_width.bold")

# Midpoint M as intersection of AB and perpendicular bisector
M = Intersect(AB, perp_bisector)
style(M, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Half-segments for midpoint equality marks
AM = Segment(A, M)
MB = Segment(M, B)
style(AM, MB, stroke="color.accent", stroke_width_px="line_width.bold", tick_count=1)

# Right angle at M
right_angle = Angle(A, M, P)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide the original AB segment to avoid double drawing
hide(AB)

# Style intersection points
style(P, Q, fill="color.aux", size_px="point_size.aux", label_visible=False)
