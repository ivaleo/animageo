# Triangle ABC
A = Point(-3, -1)
B = Point(4, -2)
C = Point(0, 3)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(A, B, C, label_visible=True)

# Choose a point P inside triangle
P = Point(-1, 0.5)
style(P, label_visible=True, label_text="$P$")

# Isogonal conjugate P* of P with respect to triangle ABC
P_star = IsogonalConjugation(A, B, C, P)
style(P_star, label_visible=True, label_text="$P^*$")

# Draw cevians from vertices through P
AP = Segment(A, P)
BP = Segment(B, P)
CP = Segment(C, P)
style(AP, BP, CP, stroke="color.aux", stroke_width_px="line_width.aux")

# Draw cevians from vertices through P_star
AP_star = Segment(A, P_star)
BP_star = Segment(B, P_star)
CP_star = Segment(C, P_star)
style(AP_star, BP_star, CP_star, stroke="color.accent", stroke_width_px="line_width.bold")

# Mark reflected angle pairs: angle between AB and AP equals angle between AP_star and AC
ang1 = Angle(B, A, P)
ang2 = Angle(P_star, A, C)
style(ang1, ang2, arc_size_px="angle_radius.main", tick_count=1)

# Angle between BC and BP equals angle between BP_star and BA
ang3 = Angle(C, B, P)
ang4 = Angle(P_star, B, A)
style(ang3, ang4, arc_size_px="angle_radius.main", tick_count=2)

# Angle between CA and CP equals angle between CP_star and CB
ang5 = Angle(A, C, P)
ang6 = Angle(P_star, C, B)
style(ang5, ang6, arc_size_px="angle_radius.main", tick_count=3)
