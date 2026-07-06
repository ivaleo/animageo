# Triangle ABC
A = Point(-3, 0)
B = Point(3, 0)
C = Point(1, 4)
style(A, B, C, label_visible=True)

# Sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Point P inside the triangle
P = Point(0, 1.5)
style(P, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Isogonal conjugate P*
P_star = IsogonalConjugation(A, B, C, P)
style(P_star, label_visible=True, label_text="$P^*$", fill="color.accent", size_px="point_size.bold")

# Cevians from P
AP = Segment(A, P)
BP = Segment(B, P)
CP = Segment(C, P)
style(AP, BP, CP, stroke="color.aux", stroke_width_px="line_width.aux")

# Cevians from P*
AP_star = Segment(A, P_star)
BP_star = Segment(B, P_star)
CP_star = Segment(C, P_star)
style(AP_star, BP_star, CP_star, stroke="color.aux", stroke_width_px="line_width.aux")

# Mark equal reflected angles at vertex A
ang_BAP = Angle(B, A, P)
ang_PAC = Angle(P, A, C)
ang_BAP_star = Angle(B, A, P_star)
ang_P_star_AC = Angle(P_star, A, C)
style(ang_BAP, ang_P_star_AC, arc_size_px="angle_radius.main", tick_count=1)
style(ang_PAC, ang_BAP_star, arc_size_px="angle_radius.main", tick_count=2)

# Mark equal reflected angles at vertex B
ang_ABP = Angle(A, B, P)
ang_PBC = Angle(P, B, C)
ang_ABP_star = Angle(A, B, P_star)
ang_P_star_BC = Angle(P_star, B, C)
style(ang_ABP, ang_P_star_BC, arc_size_px="angle_radius.main", tick_count=3)
style(ang_PBC, ang_ABP_star, arc_size_px="angle_radius.main", tick_count=4)

# Mark equal reflected angles at vertex C
ang_BCP = Angle(B, C, P)
ang_PCA = Angle(P, C, A)
ang_BCP_star = Angle(B, C, P_star)
ang_P_star_CA = Angle(P_star, C, A)
style(ang_BCP, ang_P_star_CA, arc_size_px="angle_radius.main", tick_count=5)
style(ang_PCA, ang_BCP_star, arc_size_px="angle_radius.main", tick_count=6)
