# Orthic triangle of acute triangle ABC
A = Point(-3, 2)
B = Point(3, -1)
C = Point(0, 4)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Altitude feet
D = Intersect(PerpendicularLine(A, BC), BC)
E = Intersect(PerpendicularLine(B, CA), CA)
F = Intersect(PerpendicularLine(C, AB), AB)

# Orthic triangle
orthic, DE, EF, FD = Polygon(D, E, F)

# Style main triangle
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, fill="color.main", size_px="point_size.main", label_visible=True)

# Style orthic triangle
style(orthic, fill="color.accent", fill_opacity=0.15, stroke="color.accent", stroke_width_px="line_width.bold")
style(D, E, F, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Right angle markers at feet
right_D = Angle(B, D, A)
right_E = Angle(C, E, B)
right_F = Angle(A, F, C)
style(right_D, right_E, right_F, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide altitude lines (keep only segments if needed, but feet are enough)
hide(PerpendicularLine(A, BC), PerpendicularLine(B, CA), PerpendicularLine(C, AB))
