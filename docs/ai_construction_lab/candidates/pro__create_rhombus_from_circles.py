# Free points A and B define the diagonal
A = Point(0, 0)
B = Point(4, 0)

# Equal circles centered at A and B with radius AB
circle_A = Circle(A, B)
circle_B = Circle(B, A)

# Intersection points of the circles are the other two vertices of the rhombus
C, D = Intersect(circle_A, circle_B)

# Sides of the rhombus
AC = Segment(A, C)
BC = Segment(B, C)
AD = Segment(A, D)
BD = Segment(B, D)

# Style the rhombus sides
style(AC, BC, AD, BD, stroke="color.main", stroke_width_px="line_width.main")

# Style the diagonal AB
style(Segment(A, B), stroke="color.accent", stroke_width_px="line_width.bold")

# Hide the construction circles
hide(circle_A, circle_B)

# Label vertices
style(A, B, C, D, label_visible=True)
