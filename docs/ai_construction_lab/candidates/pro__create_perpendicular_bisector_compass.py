A = Point(-2, 0)
B = Point(2, 0)
AB = Segment(A, B)
style(AB, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, label_visible=True)

radius = Distance(A, B) * 1.2
circle_A = Circle(A, radius)
circle_B = Circle(B, radius)
style(circle_A, circle_B, stroke="color.aux", stroke_width_px="line_width.aux")

P, Q = Intersect(circle_A, circle_B)
perp_bisector = Line(P, Q)
style(perp_bisector, stroke="color.accent", stroke_width_px="line_width.bold")

M = Midpoint(A, B)
style(M, fill="color.accent", size_px="point_size.bold", label_visible=True)

right_angle = Angle(A, M, P)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

hide(circle_A, circle_B)
