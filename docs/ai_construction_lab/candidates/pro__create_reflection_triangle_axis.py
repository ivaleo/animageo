# Given triangle ABC and line l
A = Point(-2, 1)
B = Point(0, -2)
C = Point(3, 0)
P = Point(-3, -1)
Q = Point(2, 3)
l = Line(P, Q)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True)

# Reflect triangle vertices across line l
A1 = Reflect(A, l)
B1 = Reflect(B, l)
C1 = Reflect(C, l)

# Reflected triangle sides
A1B1 = Segment(A1, B1)
B1C1 = Segment(B1, C1)
C1A1 = Segment(C1, A1)
style(A1B1, B1C1, C1A1, stroke="color.accent", stroke_width_px="line_width.bold")
style(A1, B1, C1, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Style the mirror line
style(l, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="5,5")
hide(P, Q)
