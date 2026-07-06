# Lemniscate of Bernoulli: (x^2 + y^2)^2 = a^2 (x^2 - y^2)
# Choose a = 2 for a visible size
lemniscate = ImplicitCurve("(x^2 + y^2)^2 - 4*(x^2 - y^2)")

# A generic line intersecting the lemniscate
# Choose a line through two points that will intersect the curve in 4 points
P = Point(-2, 1)
Q = Point(2, -1)
line = Line(P, Q)

# Intersection points (expect 4 in this configuration)
I1, I2, I3, I4 = Intersect(lemniscate, line)

# Style the lemniscate as the main curve
style(lemniscate, stroke="color.main", stroke_width_px="line_width.main")

# Style the line as secondary
style(line, stroke="color.aux", stroke_width_px="line_width.aux")

# Mark intersection points with accent color and bold size
style(I1, I2, I3, I4, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Hide the helper points used to define the line
hide(P, Q)
