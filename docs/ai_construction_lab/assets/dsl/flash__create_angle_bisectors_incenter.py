A = Point(-3, -2)
B = Point(4, -1)
C = Point(1, 3)

bis_A = AngularBisector(B, A, C)
bis_B = AngularBisector(A, B, C)
bis_C = AngularBisector(A, C, B)

I = Intersect(bis_A, bis_B)

AD = Segment(A, I)
BE = Segment(B, I)
CF = Segment(C, I)

style(A, B, C, label_visible=True)
style(I, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(AD, BE, CF, stroke="color.accent", stroke_width_px="line_width.bold")
hide(bis_A, bis_B, bis_C)

ang1 = Angle(B, A, I)
ang2 = Angle(I, A, C)
ang3 = Angle(A, B, I)
ang4 = Angle(I, B, C)
ang5 = Angle(A, C, I)
ang6 = Angle(I, C, B)
style(ang1, ang2, arc_size_px="angle_radius.main", tick_count=1)
style(ang3, ang4, arc_size_px="angle_radius.main", tick_count=2)
style(ang5, ang6, arc_size_px="angle_radius.main", tick_count=3)
