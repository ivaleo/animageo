A = Point(-3, 1)
B = Point(1, -2)
C = Point(2, 3)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True)

# Extend side AC beyond C to form the exterior angle at C
D = C + (C - A)
CD = Segment(C, D)
style(CD, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")

# Exterior angle at C: angle between extension CD and side CB
ext_angle = Angle(D, C, B)
style(ext_angle, arc_size_px="angle_radius.main", tick_count=1)

# Remote interior angles: at A and B
int_angle_A = Angle(B, A, C)
int_angle_B = Angle(A, B, C)
style(int_angle_A, int_angle_B, arc_size_px="angle_radius.main", tick_count=2)
