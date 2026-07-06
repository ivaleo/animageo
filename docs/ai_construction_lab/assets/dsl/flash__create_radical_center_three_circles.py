# Three circles with pairwise radical axes and radical center
A = Point(-3, 0)
B = Point(3, 0)
C = Point(0, 4)

# Define circles with different radii
c1 = Circle(A, 3)
c2 = Circle(B, 3)
c3 = Circle(C, 3)

# Radical axis of c1 and c2: line through their intersection points
P12, Q12 = Intersect(c1, c2)
rad12 = Line(P12, Q12)
style(rad12, stroke="color.accent", stroke_width_px="line_width.main")

# Radical axis of c2 and c3
P23, Q23 = Intersect(c2, c3)
rad23 = Line(P23, Q23)
style(rad23, stroke="color.accent", stroke_width_px="line_width.main")

# Radical axis of c1 and c3
P13, Q13 = Intersect(c1, c3)
rad13 = Line(P13, Q13)
style(rad13, stroke="color.accent", stroke_width_px="line_width.main")

# Radical center: intersection of any two radical axes
R = Intersect(rad12, rad23)
style(R, label_visible=True, label_text="$R$", fill="color.accent", size_px="point_size.bold")

# Style circles
style(c1, c2, c3, stroke="color.main", stroke_width_px="line_width.main")

# Hide intersection points used for construction
hide(P12, Q12, P23, Q23, P13, Q13)
