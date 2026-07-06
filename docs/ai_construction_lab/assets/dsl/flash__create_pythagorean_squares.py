A = Point(0, 0)
B = Point(4, 0)
C = Point(0, 3)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Right angle at A
right_angle = Angle(B, A, C)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Squares on each side
sq_AB, AB1, B1A1, A1A, A1 = Polygon(A, B, 4)
sq_BC, BC1, C1B1, B1B, B1 = Polygon(B, C, 4)
sq_CA, CA1, A1C1, C1C, C1 = Polygon(C, A, 4)

# Style squares with different fills
style(sq_AB, fill="color.accent", fill_opacity=0.3)
style(sq_BC, fill="color.strong", fill_opacity=0.3)
style(sq_CA, fill="color.aux", fill_opacity=0.3)

# Label vertices
style(A, B, C, label_visible=True)

# Hide square vertices that are not part of the triangle
hide(A1, B1, C1)

# Mark equal sides? Not requested, so skip.
