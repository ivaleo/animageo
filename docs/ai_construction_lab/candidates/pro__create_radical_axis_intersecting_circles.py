# Two intersecting circles and their radical axis

# Centers
O1 = Point(-2, 0)
O2 = Point(2, 0)

# Radii chosen so circles intersect
r1 = 3
r2 = 3

# Points on circles to define them
P1 = Point(-2 + r1, 0)
P2 = Point(2 + r2, 0)

# Circles
c1 = Circle(O1, P1)
c2 = Circle(O2, P2)

# Intersection points of the circles
A, B = Intersect(c1, c2)

# Radical axis: line through intersection points
radical_axis = Line(A, B)

# Style
style(O1, O2, label_visible=True, fill="color.main", size_px="point_size.main")
style(c1, c2, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(radical_axis, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide helper points used only to define circles
hide(P1, P2)
