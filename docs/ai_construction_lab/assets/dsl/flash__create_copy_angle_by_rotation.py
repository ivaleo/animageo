A = Point(0, 0)
B = Point(4, 0)
C = Point(1, 3)
P = Point(6, 0)
Q = Point(9, 0)

# Source angle
AB = Segment(A, B)
AC = Segment(A, C)

# Target ray
PQ = Ray(P, Q)

# Copy angle by rotation: rotate Q around P by angle BAC
angle_size = AngleSize(B, A, C)
Q_rot = Rotate(Q, angle_size, P)

# Copied ray
PR = Ray(P, Q_rot)

# Mark equal angles
angle_src = Angle(B, A, C)
angle_copied = Angle(Q, P, Q_rot)
style(angle_src, angle_copied, tick_count=1, arc_size_px="angle_radius.main")

# Style
style(A, B, C, P, Q, Q_rot, label_visible=True)
style(AB, AC, stroke="color.main", stroke_width_px="line_width.main")
style(PQ, PR, stroke="color.accent", stroke_width_px="line_width.bold")
