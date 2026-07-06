# Given circle with center O and external point P
O = Point(0, 0)
A = Point(2, 0)
circle = Circle(O, A)
P = Point(5, 1)

# First secant line through P intersecting circle at B and C
B = Point(3, 1.5)
line1 = Line(P, B)
B, C = Intersect(line1, circle)

# Second secant line through P intersecting circle at D and E
D = Point(3, -0.5)
line2 = Line(P, D)
D, E = Intersect(line2, circle)

# Draw visible segments: secant segments from P to circle intersection points
PB = Segment(P, B)
PC = Segment(P, C)
PD = Segment(P, D)
PE = Segment(P, E)

# Style
style(O, A, label_visible=False)
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(P, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(B, C, D, E, label_visible=True, fill="color.main", size_px="point_size.main")
style(PB, PC, PD, PE, stroke="color.accent", stroke_width_px="line_width.bold")
hide(line1, line2)
