A = Point(0, 0)
B = Point(4, 0)
AB = Segment(A, B)

# Build square ABCD on AB: rotate B around A by 90° to get D, then rotate A around B by -90° to get C
D = Rotate(B, pi/2, A)
C = Rotate(A, -pi/2, B)

# Square sides
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Mark right angles at each vertex
angleA = Angle(D, A, B)
angleB = Angle(A, B, C)
angleC = Angle(B, C, D)
angleD = Angle(C, D, A)
style(angleA, angleB, angleC, angleD, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Mark equal sides (all four sides equal)
style(AB, BC, CD, DA, tick_count=1)

# Style square sides
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")

# Label vertices
style(A, B, C, D, label_visible=True)
