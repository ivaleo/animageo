# Butterfly theorem configuration
# Circle with center O, chord PQ with midpoint M, chords AB and CD through M

O = Point(0, 0)
P = Point(-2.1, 1.7)
Q = Point(2.1, 1.7)
circle = Circle(O, P)

# Chord PQ and its midpoint M
PQ = Segment(P, Q)
M = Midpoint(P, Q)

# Chords AB and CD through M
# Choose directions for the chords
A_dir = Point(1.5, 2.5)
C_dir = Point(-1.5, 2.5)

line_AB = Line(M, A_dir)
line_CD = Line(M, C_dir)

A, B = Intersect(line_AB, circle)
C, D = Intersect(line_CD, circle)

AB = Segment(A, B)
CD = Segment(C, D)

# Style
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(PQ, AB, CD, stroke="color.accent", stroke_width_px="line_width.bold")
style(M, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(P, Q, A, B, C, D, label_visible=True)
hide(O, A_dir, C_dir, line_AB, line_CD)
