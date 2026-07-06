# Orthic triangle of acute triangle ABC
# Free points A, B, C in generic acute configuration
A = Point(-3, 2)
B = Point(3, 1)
C = Point(0, 5)

# Triangle sides as visible segments
tri, AB, BC, CA = Polygon(A, B, C)
style(tri, fill_opacity=0.05, stroke="color.main", stroke_width_px="line_width.main")

# Altitude from A to BC
line_BC = Line(B, C)
alt_A = PerpendicularLine(A, line_BC)
D = Intersect(alt_A, line_BC)
AD = Segment(A, D)

# Altitude from B to CA
line_CA = Line(C, A)
alt_B = PerpendicularLine(B, line_CA)
E = Intersect(alt_B, line_CA)
BE = Segment(B, E)

# Altitude from C to AB
line_AB = Line(A, B)
alt_C = PerpendicularLine(C, line_AB)
F = Intersect(alt_C, line_AB)
CF = Segment(C, F)

# Orthic triangle DEF
orthic, DE, EF, FD = Polygon(D, E, F)
style(orthic, fill_opacity=0.1, stroke="color.accent", stroke_width_px="line_width.bold")

# Right angle markers at feet
right_D = Angle(B, D, A)
right_E = Angle(C, E, B)
right_F = Angle(A, F, C)
style(right_D, right_E, right_F, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide infinite altitude lines and side lines
hide(alt_A, alt_B, alt_C, line_BC, line_CA, line_AB)

# Style altitude segments as auxiliary
style(AD, BE, CF, stroke="color.aux", stroke_width_px="line_width.aux")

# Label vertices and feet
style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(D, E, F, label_visible=True, fill="color.accent", size_px="point_size.bold")
