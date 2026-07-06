A = Point(-4, -2)
B = Point(4, -1)
C = Point(0, 4)
style(A, B, C, label_visible=True)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

bis_A = AngularBisector(B, A, C)
bis_B = AngularBisector(A, B, C)
bis_C = AngularBisector(A, C, B)

D = Intersect(bis_A, BC)
E = Intersect(bis_B, CA)
F = Intersect(bis_C, AB)

AD = Segment(A, D)
BE = Segment(B, E)
CF = Segment(C, F)
style(AD, BE, CF, stroke="color.accent", stroke_width_px="line_width.bold")

I = Intersect(bis_A, bis_B)
style(I, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$I$")

hide(bis_A, bis_B, bis_C)

ang1 = Angle(B, A, D)
ang2 = Angle(D, A, C)
ang3 = Angle(A, B, E)
ang4 = Angle(E, B, C)
ang5 = Angle(A, C, F)
ang6 = Angle(F, C, B)
style(ang1, ang2, ang3, ang4, ang5, ang6, arc_size_px="angle_radius.main", tick_count=1)
