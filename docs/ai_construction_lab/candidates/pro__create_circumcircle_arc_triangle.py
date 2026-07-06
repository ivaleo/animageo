# Given points A, B, C
A = Point(-2, 1)
B = Point(0, 3)
C = Point(2, 1)

# Construct the circle through A, B, C
circle = Circle(A, B, C)

# The arc from A to C passing through B (upper arc)
arc = CircleArc(circle.center, A, C)

# Style the arc
style(arc, stroke="color.accent", stroke_width_px="line_width.bold")

# Show points and labels
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")
style(B, fill="color.accent", size_px="point_size.bold")

# Hide the full circle to show only the arc
hide(circle)
