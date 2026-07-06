# Two parallel lines and a transversal with alternate interior angles marked
A = Point(-3, 2)
B = Point(3, 2)
C = Point(-2, -2)
D = Point(2, -2)

l1 = Line(A, B)
l2 = Line(C, D)

# Transversal through points on the two lines
E = Point(-1, 2)
F = Point(1, -2)
trans = Line(E, F)

# Intersection points
P = Intersect(l1, trans)
Q = Intersect(l2, trans)

# Mark alternate interior angles
# At P: angle between l1 (to the right) and trans (downward)
# At Q: angle between l2 (to the left) and trans (upward)
# These are alternate interior angles.

# For angle at P: vertex P, arms along l1 (right) and trans (down)
# Use points: on l1 to the right of P, e.g., B; on trans below P, e.g., Q
ang1 = Angle(B, P, Q)

# For angle at Q: vertex Q, arms along l2 (left) and trans (up)
# Use points: on l2 to the left of Q, e.g., C; on trans above Q, e.g., P
ang2 = Angle(C, Q, P)

# Style
style(l1, l2, stroke="color.main", stroke_width_px="line_width.main")
style(trans, stroke="color.aux", stroke_width_px="line_width.aux")
style(ang1, ang2, arc_size_px="angle_radius.main", tick_count=1, stroke="color.accent", stroke_width_px="line_width.bold")
style(P, Q, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Hide helper points used only to define lines
hide(A, B, C, D, E, F)
