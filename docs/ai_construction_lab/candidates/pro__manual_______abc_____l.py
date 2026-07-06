# Obtuse triangle ABC with obtuse angle at C
A = Point(-3, 2)
B = Point(3, 2)
C = Point(0, 0)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Exterior angle at C: extend side AC beyond C
D = C + (C - A)
CD = Segment(C, D)

# Exterior angle bisector l at C (bisector of angle BCD)
l = AngularBisector(B, C, D)

# Circle centered at B tangent to line l
# Tangent point T is foot of perpendicular from B to l
perp = PerpendicularLine(B, l)
T = Intersect(perp, l)
circle = Circle(B, T)

# Style
style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(CD, stroke="color.aux", stroke_width_px="line_width.aux")
style(l, stroke="color.accent", stroke_width_px="line_width.bold", label_visible=True, label_text="$l$")
style(circle, stroke="color.accent", stroke_width_px="line_width.bold")
style(T, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Right angle marker at T
right_angle = Angle(B, T, C)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide helpers
hide(perp, D)
