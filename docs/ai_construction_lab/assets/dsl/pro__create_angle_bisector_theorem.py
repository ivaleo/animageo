# Triangle ABC
A = Point(2, 5)
B = Point(0, 0)
C = Point(6, 0)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, CA, stroke="color.main", stroke_width_px="line_width.main")
style(BC, stroke="color.main", stroke_width_px="line_width.main")

# Angle bisector from A to BC
bisector = AngularBisector(B, A, C)
D = Intersect(bisector, BC)
hide(bisector)

AD = Segment(A, D)
style(AD, stroke="color.accent", stroke_width_px="line_width.bold")

# Subsegments BD and DC
BD = Segment(B, D)
DC = Segment(D, C)
style(BD, DC, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide original BC to avoid double border
hide(BC)

# Labels
style(A, B, C, D, label_visible=True)
style(AD, label_visible=True, label_text="AD")
style(BD, label_visible=True, label_text="BD")
style(DC, label_visible=True, label_text="DC")

# Angle marks to show bisector
ang1 = Angle(B, A, D)
ang2 = Angle(D, A, C)
style(ang1, ang2, arc_size_px="angle_radius.main", tick_count=1)
