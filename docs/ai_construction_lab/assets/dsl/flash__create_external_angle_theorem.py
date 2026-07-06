A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 3)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
# Extend side AC beyond C to create exterior angle at C
D = C + (C - A)
CD = Segment(C, D)
# Exterior angle at C: angle between BC and CD
ext_angle = Angle(B, C, D)
style(ext_angle, arc_size_px="angle_radius.main", tick_count=1)
# Remote interior angles
int1 = Angle(B, A, C)
int2 = Angle(A, B, C)
style(int1, int2, arc_size_px="angle_radius.main", tick_count=2)
# Mark equal arcs for remote interior angles (same tick_count)
style(int1, int2, tick_count=2)
# Labels
style(A, B, C, label_visible=True)
style(D, label_visible=True, label_text="$D$")
# Hide extension line beyond D if needed (keep CD visible)
# Ensure triangle sides are visible
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(CD, stroke="color.aux", stroke_width_px="line_width.aux")
