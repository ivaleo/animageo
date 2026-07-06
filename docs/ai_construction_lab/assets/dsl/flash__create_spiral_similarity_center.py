# Two intersecting circles and spiral similarity center
O1 = Point(-1.5, 0)
O2 = Point(1.5, 0)
r = 2.5
c1 = Circle(O1, r)
c2 = Circle(O2, r)

# Intersection points of the circles
P, Q = Intersect(c1, c2)
style(P, Q, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Choose a chord in each circle through P (spiral center)
# Chord in c1: through P and another point on c1
A = Rotate(P, 0.8, O1)
B = Rotate(P, -0.5, O1)
chord1 = Segment(A, B)
style(chord1, stroke="color.main", stroke_width_px="line_width.main")

# Chord in c2: through P and another point on c2
C = Rotate(P, 1.2, O2)
D = Rotate(P, -0.3, O2)
chord2 = Segment(C, D)
style(chord2, stroke="color.main", stroke_width_px="line_width.main")

# Mark the spiral similarity center P
style(P, label_visible=True, label_text="$P$", fill="color.accent", size_px="point_size.bold")

# Optionally hide the circles if not needed, but keep them visible for context
style(c1, c2, stroke="color.aux", stroke_width_px="line_width.aux")
