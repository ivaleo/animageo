# Copy angle BAC to vertex P on ray PQ

# Given: angle BAC and ray PQ
A = Point(0, 0)
B = Point(3, 1)
C = Point(2, 3)
P = Point(5, 0)
Q = Point(8, 1)

# Draw given angle BAC
AB = Ray(A, B)
AC = Ray(A, C)
ang_BAC = Angle(B, A, C)
style(ang_BAC, arc_size_px="angle_radius.main", tick_count=1)

# Draw given ray PQ
ray_PQ = Ray(P, Q)

# Copy angle BAC to vertex P on ray PQ by rotation
# Rotate Q around P by the measure of angle BAC
ang_size = AngleSize(B, A, C)
R = Rotate(Q, ang_size, P)

# Draw copied ray PR
PR = Ray(P, R)

# Mark copied angle QPR
ang_QPR = Angle(Q, P, R)
style(ang_QPR, arc_size_px="angle_radius.main", tick_count=1)

# Style
style(AB, AC, ray_PQ, PR, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, P, Q, R, label_visible=True, fill="color.main", size_px="point_size.main")
style(ang_BAC, ang_QPR, stroke="color.accent", stroke_width_px="line_width.bold")
