# Build a unit circle centered at origin
O = Point(0, 0)
A = Point(1, 0)
circle = Circle(O, A)

# Build sine function
sine = Function("sin(x)")

# Intersect sine and circle
# The sine curve and unit circle intersect at points where x satisfies sin(x) = ±sqrt(1 - x^2)
# For a typical view, we'll find intersections in the range [-2π, 2π]
# Use Intersect to find all intersection points in the visible range
intersections = Intersect(sine, circle)

# Style the circle and sine curve
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(sine, stroke="color.accent", stroke_width_px="line_width.bold")

# Mark intersection points
style(intersections, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Hide the point A used to define the circle
hide(A)
