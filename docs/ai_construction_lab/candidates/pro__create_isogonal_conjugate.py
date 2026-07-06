# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Point P inside the triangle
P = Point(0, 1)
style(P, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Isogonal conjugate P* of P with respect to triangle ABC
P_star = IsogonalConjugation(A, B, C, P)
style(P_star, label_visible=True, label_text="$P^*$", fill="color.accent", size_px="point_size.bold")

# Cevians from vertices through P
AP = Segment(A, P)
BP = Segment(B, P)
CP = Segment(C, P)
style(AP, BP, CP, stroke="color.aux", stroke_width_px="line_width.aux")

# Cevians from vertices through P*
AP_star = Segment(A, P_star)
BP_star = Segment(B, P_star)
CP_star = Segment(C, P_star)
style(AP_star, BP_star, CP_star, stroke="color.aux", stroke_width_px="line_width.aux")
