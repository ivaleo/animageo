# Three circles and their radical axes, with radical center

# Centers
O1 = Point(-3, 0)
O2 = Point(3, 0)
O3 = Point(0, 4)

# Radii
r1 = 2.5
r2 = 2.5
r3 = 2.0

# Circles
c1 = Circle(O1, r1)
c2 = Circle(O2, r2)
c3 = Circle(O3, r3)

# Radical axes (line through intersection points of each pair)
# For c1 and c2: symmetric about y-axis, radical axis is x=0
rad12 = Line(Point(0, -3), Point(0, 3))
# For c1 and c3: compute intersection of circles
# Solve (x+3)^2 + y^2 = 6.25 and x^2 + (y-4)^2 = 4
# Subtract: (x+3)^2 + y^2 - x^2 - (y-4)^2 = 2.25
# => 6x + 9 + 8y - 16 = 2.25 => 6x + 8y = 9.25 => 3x + 4y = 4.625
# Radical axis line: 3x + 4y = 4.625
# Choose two points on this line
rad13 = Line(Point(-1, 1.90625), Point(1, 0.40625))
# For c2 and c3: similar
# (x-3)^2 + y^2 = 6.25 and x^2 + (y-4)^2 = 4
# => -6x + 9 + 8y - 16 = 2.25 => -6x + 8y = 9.25 => 3x - 4y = -4.625
rad23 = Line(Point(-1, 0.40625), Point(1, 1.90625))

# Radical center: intersection of any two radical axes
RC = Intersect(rad12, rad13)

# Style
style(c1, c2, c3, stroke="color.main", stroke_width_px="line_width.main")
style(O1, O2, O3, fill="color.main", size_px="point_size.main", label_visible=True)
style(rad12, rad23, rad13, stroke="color.accent", stroke_width_px="line_width.bold")
style(RC, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$RC$")
