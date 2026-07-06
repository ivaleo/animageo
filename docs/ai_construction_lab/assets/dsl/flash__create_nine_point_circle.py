A = Point(-3, -2)
B = Point(4, -1)
C = Point(1, 4)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Altitudes
alt_A = PerpendicularLine(A, BC)
foot_A = Intersect(alt_A, BC)
style(foot_A, label_visible=True, label_text="$H_A$", fill="color.accent", size_px="point_size.bold")
right_A = Angle(B, foot_A, A)
style(right_A, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(alt_A)

alt_B = PerpendicularLine(B, CA)
foot_B = Intersect(alt_B, CA)
style(foot_B, label_visible=True, label_text="$H_B$", fill="color.accent", size_px="point_size.bold")
right_B = Angle(C, foot_B, B)
style(right_B, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(alt_B)

alt_C = PerpendicularLine(C, AB)
foot_C = Intersect(alt_C, AB)
style(foot_C, label_visible=True, label_text="$H_C$", fill="color.accent", size_px="point_size.bold")
right_C = Angle(A, foot_C, C)
style(right_C, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(alt_C)

# Orthocenter
H = Intersect(alt_A, alt_B)
style(H, label_visible=True, label_text="$H$", fill="color.accent", size_px="point_size.bold")

# Midpoints of sides
M_AB = Midpoint(A, B)
M_BC = Midpoint(B, C)
M_CA = Midpoint(C, A)
style(M_AB, M_BC, M_CA, label_visible=True, fill="color.main", size_px="point_size.main")

# Midpoints from vertices to orthocenter
M_AH = Midpoint(A, H)
M_BH = Midpoint(B, H)
M_CH = Midpoint(C, H)
style(M_AH, M_BH, M_CH, label_visible=True, fill="color.main", size_px="point_size.main")

# Nine-point circle through three midpoints of sides
nine_circle = Circle(M_AB, M_BC, M_CA)
style(nine_circle, stroke="color.accent", stroke_width_px="line_width.bold")

# Mark equal segments on sides (midpoint halves)
AM_AB = Segment(A, M_AB)
M_ABB = Segment(M_AB, B)
style(AM_AB, M_ABB, tick_count=1, stroke_width_px=0)
BM_BC = Segment(B, M_BC)
M_BCC = Segment(M_BC, C)
style(BM_BC, M_BCC, tick_count=2, stroke_width_px=0)
CM_CA = Segment(C, M_CA)
M_CAA = Segment(M_CA, A)
style(CM_CA, M_CAA, tick_count=3, stroke_width_px=0)

# Mark equal segments from vertices to orthocenter midpoints
AM_AH = Segment(A, M_AH)
M_AHH = Segment(M_AH, H)
style(AM_AH, M_AHH, tick_count=4, stroke_width_px=0)
BM_BH = Segment(B, M_BH)
M_BHH = Segment(M_BH, H)
style(BM_BH, M_BHH, tick_count=5, stroke_width_px=0)
CM_CH = Segment(C, M_CH)
M_CHH = Segment(M_CH, H)
style(CM_CH, M_CHH, tick_count=6, stroke_width_px=0)

# Hide altitude lines (already hidden)
# Show triangle sides
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Labels for vertices
style(A, B, C, label_visible=True)

# Labels for midpoints of sides
style(M_AB, label_text="$M_{AB}$")
style(M_BC, label_text="$M_{BC}$")
style(M_CA, label_text="$M_{CA}$")

# Labels for midpoints to orthocenter
style(M_AH, label_text="$M_{AH}$")
style(M_BH, label_text="$M_{BH}$")
style(M_CH, label_text="$M_{CH}$")
