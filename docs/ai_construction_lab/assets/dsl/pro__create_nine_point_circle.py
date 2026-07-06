# Triangle ABC
A = Point(-4, -2)
B = Point(4, -2)
C = Point(0, 5)
style(A, B, C, label_visible=True)

# Sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Midpoints of sides
D = Midpoint(A, B)
E = Midpoint(B, C)
F = Midpoint(C, A)
style(D, E, F, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Altitudes and feet
# Altitude from A to BC
line_BC = Line(B, C)
alt_A = PerpendicularLine(A, line_BC)
H_A = Intersect(alt_A, line_BC)
# Altitude from B to CA
line_CA = Line(C, A)
alt_B = PerpendicularLine(B, line_CA)
H_B = Intersect(alt_B, line_CA)
# Altitude from C to AB
line_AB = Line(A, B)
alt_C = PerpendicularLine(C, line_AB)
H_C = Intersect(alt_C, line_AB)

# Orthocenter
H = Intersect(alt_A, alt_B)
style(H, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Midpoints of segments from vertices to orthocenter
G = Midpoint(A, H)
I = Midpoint(B, H)
J = Midpoint(C, H)
style(G, I, J, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Nine-point circle (through D, E, F)
nine_point_circle = Circle(D, E, F)
style(nine_point_circle, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide helper lines
hide(line_BC, line_CA, line_AB, alt_A, alt_B, alt_C)

# Mark right angles at feet
right_angle_A = Angle(B, H_A, A)
right_angle_B = Angle(C, H_B, B)
right_angle_C = Angle(A, H_C, C)
style(right_angle_A, right_angle_B, right_angle_C, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Style feet
style(H_A, H_B, H_C, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Notes
# The nine-point circle passes through D, E, F, H_A, H_B, H_C, G, I, J.
# Right-angle markers are shown at feet.
# All nine points are labeled and highlighted.
