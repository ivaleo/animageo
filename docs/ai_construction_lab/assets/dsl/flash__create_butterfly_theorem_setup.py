# Butterfly theorem configuration
# Circle with center O, chord PQ with midpoint M, chords AB and CD through M
O = Point(0, 0)
P = Point(-4, 0)
Q = Point(4, 0)
circle = Circle(O, P)
M = Midpoint(P, Q)
PQ = Segment(P, Q)
style(M, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Choose two lines through M with different slopes
line1 = Line(M, Point(1, 2))
line2 = Line(M, Point(1, -2))

# Intersect with circle to get A, B and C, D
A, B = Intersect(line1, circle)
C, D = Intersect(line2, circle)

# Draw chords
AB = Segment(A, B)
CD = Segment(C, D)

# Style: hide helper lines, keep chords visible
hide(line1, line2)
style(AB, CD, stroke="color.accent", stroke_width_px="line_width.bold")
style(PQ, stroke="color.aux", stroke_width_px="line_width.aux")
style(A, B, C, D, label_visible=True, fill="color.main", size_px="point_size.main")
style(P, Q, label_visible=True, fill="color.main", size_px="point_size.main")
