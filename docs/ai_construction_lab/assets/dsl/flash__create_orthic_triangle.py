A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(A, B, C, label_visible=True)

# altitudes
line_BC = Line(B, C)
alt_A = PerpendicularLine(A, line_BC)
HA = Intersect(alt_A, line_BC)

line_CA = Line(C, A)
alt_B = PerpendicularLine(B, line_CA)
HB = Intersect(alt_B, line_CA)

line_AB = Line(A, B)
alt_C = PerpendicularLine(C, line_AB)
HC = Intersect(alt_C, line_AB)

# orthic triangle sides
HA_HB = Segment(HA, HB)
HB_HC = Segment(HB, HC)
HC_HA = Segment(HC, HA)

# style orthic triangle
style(HA_HB, HB_HC, HC_HA, stroke="color.accent", stroke_width_px="line_width.bold")
style(HA, HB, HC, label_visible=True, fill="color.accent", size_px="point_size.bold")

# right angle markers
right1 = Angle(A, HA, B)
style(right1, right_angle_marker=True, right_angle_size_px="angle_radius.right")
right2 = Angle(B, HB, C)
style(right2, right_angle_marker=True, right_angle_size_px="angle_radius.right")
right3 = Angle(C, HC, A)
style(right3, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# hide altitude lines
hide(alt_A, alt_B, alt_C, line_BC, line_CA, line_AB)
