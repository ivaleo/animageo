# Sine function and unit circle with intersection points

# Unit circle centered at origin
O = Point(0, 0)
A = Point(1, 0)
circle = Circle(O, A)

# Sine function
sine = Function("sin(x)")

# Intersection points between sine and circle
# Circle equation: x^2 + y^2 = 1, y = sin(x)
# We'll find intersections in the visible range
P1, P2 = Intersect(sine, circle)

# Style the circle and sine
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(sine, stroke="color.accent", stroke_width_px="line_width.bold")

# Style intersection points
style(P1, P2, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Hide the circle center and radius point
hide(O, A)
