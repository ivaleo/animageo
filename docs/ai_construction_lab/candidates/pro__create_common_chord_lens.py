# Two intersecting circles, their common chord, and the lens between them.

# Free points: centers and one point on the first circle.
O1 = Point(-2, 0)
O2 = Point(2, 0)
A = Point(-2, 2.5)

# Circles
c1 = Circle(O1, A)
c2 = Circle(O2, A)  # same radius for simplicity; circles intersect

# Intersection points of the circles (common chord endpoints)
P, Q = Intersect(c1, c2)

# Common chord
chord = Segment(P, Q)

# Lens: the two circular arcs between P and Q.
# Use CircleArc with center and two endpoints. Order determines which arc.
# For the upper arc (counterclockwise from P to Q on c1)
arc1 = CircleArc(O1, P, Q)
# For the lower arc (clockwise from P to Q on c2, i.e., counterclockwise from Q to P on c2)
arc2 = CircleArc(O2, Q, P)

# Style
style(O1, O2, label_visible=True, fill="color.main", size_px="point_size.main")
style(A, label_visible=False, fill="color.aux", size_px="point_size.aux")
style(c1, c2, stroke="color.main", stroke_width_px="line_width.main")
style(chord, stroke="color.accent", stroke_width_px="line_width.bold")
style(arc1, arc2, stroke="color.accent", stroke_width_px="line_width.bold", fill="color.aux", fill_opacity=0.2)
style(P, Q, label_visible=True, fill="color.accent", size_px="point_size.bold")
