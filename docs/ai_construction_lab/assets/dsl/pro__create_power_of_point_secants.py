# Two secants from external point P to a circle

# Circle center and radius
O = Point(0, 0)
A = Point(2, 0)
circle = Circle(O, A)

# External point P
P = Point(4, 2)

# First secant line through P and two points on circle
# Choose a direction for first secant
Q1 = Point(1, 2.5)
secant1_line = Line(P, Q1)

# Intersections of first secant with circle
A1, B1 = Intersect(secant1_line, circle)

# Second secant line through P and two other points on circle
# Choose a different direction
Q2 = Point(1, -1.5)
secant2_line = Line(P, Q2)

# Intersections of second secant with circle
C1, D1 = Intersect(secant2_line, circle)

# Draw secant segments from P to the far intersection points
PA1 = Segment(P, A1)
PB1 = Segment(P, B1)
PC1 = Segment(P, C1)
PD1 = Segment(P, D1)

# Style the circle
style(circle, stroke="color.main", stroke_width_px="line_width.main")

# Style the secant lines (hide infinite lines, show segments)
hide(secant1_line, secant2_line)
style(PA1, PB1, PC1, PD1, stroke="color.accent", stroke_width_px="line_width.bold")

# Style points
style(O, A, fill="color.main", size_px="point_size.main", label_visible=False)
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(A1, B1, C1, D1, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Label intersection points with subscripts
style(A1, label_text="$A_1$")
style(B1, label_text="$B_1$")
style(C1, label_text="$C_1$")
style(D1, label_text="$D_1$")
