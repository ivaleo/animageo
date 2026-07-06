# Right triangle with circumcenter at midpoint of hypotenuse
A = Point(0, 0)
B = Point(6, 0)
C = Point(0, 4)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Right angle at A
right_angle = Angle(B, A, C)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Midpoint of hypotenuse BC
M = Midpoint(B, C)

# Circumcircle: center M, radius MB
circumcircle = Circle(M, B)

# Radii from M to vertices
MA = Segment(M, A)
MB = Segment(M, B)
MC = Segment(M, C)

# Style radii as equal with matching tick_count
style(MA, MB, MC, stroke="color.accent", stroke_width_px="line_width.bold", tick_count=1)

# Style triangle sides
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Style circumcircle
style(circumcircle, stroke="color.aux", stroke_width_px="line_width.aux")

# Labels
style(A, B, C, M, label_visible=True)
style(M, fill="color.accent", size_px="point_size.bold")
