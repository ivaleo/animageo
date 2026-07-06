A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Altitude from A to BC
line_BC = Line(B, C)
alt_A = PerpendicularLine(A, line_BC)
HA = Intersect(alt_A, line_BC)
seg_alt_A = Segment(A, HA)
right_A = Angle(B, HA, A)
style(right_A, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(line_BC, alt_A)

# Altitude from B to CA
line_CA = Line(C, A)
alt_B = PerpendicularLine(B, line_CA)
HB = Intersect(alt_B, line_CA)
seg_alt_B = Segment(B, HB)
right_B = Angle(C, HB, B)
style(right_B, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(line_CA, alt_B)

# Altitude from C to AB
line_AB = Line(A, B)
alt_C = PerpendicularLine(C, line_AB)
HC = Intersect(alt_C, line_AB)
seg_alt_C = Segment(C, HC)
right_C = Angle(A, HC, C)
style(right_C, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(line_AB, alt_C)

# Orthocenter H
H = Intersect(alt_A, alt_B)
style(H, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Style altitudes
style(seg_alt_A, seg_alt_B, seg_alt_C, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide altitude feet labels
style(HA, HB, HC, label_visible=False, size_px="point_size.aux")
