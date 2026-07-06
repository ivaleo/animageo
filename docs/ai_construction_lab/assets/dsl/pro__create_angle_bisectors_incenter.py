A = Point(0, 0)
B = Point(6, 1)
C = Point(2, 5)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

bis_A = AngularBisector(B, A, C)
bis_B = AngularBisector(C, B, A)
bis_C = AngularBisector(A, C, B)

D = Intersect(bis_A, BC)
E = Intersect(bis_B, CA)
F = Intersect(bis_C, AB)

AD = Segment(A, D)
BE = Segment(B, E)
CF = Segment(C, F)

I = Intersect(AD, BE)

style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(AD, BE, CF, stroke="color.accent", stroke_width_px="line_width.bold")

ang_A1 = Angle(B, A, D)
ang_A2 = Angle(D, A, C)
ang_B1 = Angle(C, B, E)
ang_B2 = Angle(E, B, A)
ang_C1 = Angle(A, C, F)
ang_C2 = Angle(F, C, B)

style(ang_A1, ang_A2, arc_size_px="angle_radius.main", tick_count=1)
style(ang_B1, ang_B2, arc_size_px="angle_radius.main", tick_count=2)
style(ang_C1, ang_C2, arc_size_px="angle_radius.main", tick_count=3)

style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(I, label_visible=True, fill="color.accent", size_px="point_size.bold")

hide(bis_A, bis_B, bis_C)
