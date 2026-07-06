# Triangle ABC
A = Point(-4, -1)
B = Point(4, -1)
C = Point(1, 4)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Orthocenter H: altitudes from A and B
# Altitude from A to BC
line_BC = Line(B, C)
alt_A_line = PerpendicularLine(A, line_BC)
foot_A = Intersect(alt_A_line, line_BC)
alt_A = Segment(A, foot_A)

# Altitude from B to CA
line_CA = Line(C, A)
alt_B_line = PerpendicularLine(B, line_CA)
foot_B = Intersect(alt_B_line, line_CA)
alt_B = Segment(B, foot_B)

H = Intersect(alt_A_line, alt_B_line)

# Circumcenter O: perpendicular bisectors of AB and BC
mid_AB = Midpoint(A, B)
perp_AB = PerpendicularBisector(A, B)

mid_BC = Midpoint(B, C)
perp_BC = PerpendicularBisector(B, C)

O = Intersect(perp_AB, perp_BC)

# Circumcircle
circumcircle = Circle(O, A)

# Nine-point circle center N: midpoint of OH
N = Midpoint(O, H)

# Nine-point circle: through midpoints of sides
mid_CA = Midpoint(C, A)
nine_point_circle = Circle(N, mid_AB)

# Euler line
Euler_line = Line(O, H)

# Style
style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

style(H, O, N, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(H, label_text="$H$")
style(O, label_text="$O$")
style(N, label_text="$N$")

style(alt_A, alt_B, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")
style(foot_A, foot_B, fill="color.aux", size_px="point_size.aux", label_visible=False)

style(perp_AB, perp_BC, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")
style(mid_AB, mid_BC, mid_CA, fill="color.aux", size_px="point_size.aux", label_visible=False)

style(circumcircle, stroke="color.aux", stroke_width_px="line_width.aux")
style(nine_point_circle, stroke="color.accent", stroke_width_px="line_width.main")

style(Euler_line, stroke="color.accent", stroke_width_px="line_width.bold")

# Right angle markers at altitude feet
right_angle_A = Angle(B, foot_A, A)
right_angle_B = Angle(C, foot_B, B)
style(right_angle_A, right_angle_B, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hide helper lines
hide(line_BC, line_CA, alt_A_line, alt_B_line)
