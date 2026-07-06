# Define triangle ABC with obtuse angle at C
A = Point(-3, 0)
B = Point(3, 0)
C = Point(0.5, 2)

# Sides of triangle
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Extend side AC beyond C to form exterior angle at C
# Direction from A to C: C - A, extend beyond C
ext_dir = C - A
D = C + ext_dir
CD = Segment(C, D)

# Exterior angle at C: between BC and CD
# Construct angle bisector of exterior angle (angle between BC and CD)
# AngularBisector(arm1, vertex, arm2) where vertex is C
bisector_line = AngularBisector(B, C, D)

# Circle with center B tangent to bisector_line
# Tangent point: foot of perpendicular from B to bisector_line
perp_line = PerpendicularLine(B, bisector_line)
T = Intersect(perp_line, bisector_line)

# Circle centered at B through T
circle = Circle(B, T)

# Mark right angle at tangent point
right_angle = Angle(B, T, C)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Style: hide construction helpers, show result
hide(bisector_line, perp_line, CD)
style(circle, stroke="color.accent", stroke_width_px="line_width.bold")
style(T, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$T$")
style(A, B, C, label_visible=True)
