# Three circles with centers O1, O2, O3 and radii r1, r2, r3
O1 = Point(-3, 0)
O2 = Point(3, 0)
O3 = Point(0, 4)

# Define radii
r1 = 2.5
r2 = 2.5
r3 = 3.0

# Points on circles to define them
P1 = Point(O1.x + r1, O1.y)
P2 = Point(O2.x + r2, O2.y)
P3 = Point(O3.x, O3.y + r3)

# Circles
c1 = Circle(O1, P1)
c2 = Circle(O2, P2)
c3 = Circle(O3, P3)

# Style circles
style(c1, c2, c3, stroke="color.main", stroke_width_px="line_width.main")

# Radical axes: line through intersection points of each pair
# Pair (c1, c2)
I12_1, I12_2 = Intersect(c1, c2)
rad12 = Line(I12_1, I12_2)
style(rad12, stroke="color.accent", stroke_width_px="line_width.bold")

# Pair (c1, c3)
I13_1, I13_2 = Intersect(c1, c3)
rad13 = Line(I13_1, I13_2)
style(rad13, stroke="color.accent", stroke_width_px="line_width.bold")

# Pair (c2, c3)
I23_1, I23_2 = Intersect(c2, c3)
rad23 = Line(I23_1, I23_2)
style(rad23, stroke="color.accent", stroke_width_px="line_width.bold")

# Radical center: intersection of any two radical axes
R = Intersect(rad12, rad13)
style(R, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Hide intersection points used only for construction
hide(I12_1, I12_2, I13_1, I13_2, I23_1, I23_2)

# Optionally label centers
style(O1, O2, O3, label_visible=True, fill="color.main", size_px="point_size.main")
