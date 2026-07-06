A = Point(-4, -2)
B = Point(4, -2)
C = Point(0, 4)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

D = Midpoint(A, B)
E = Midpoint(B, C)
F = Midpoint(C, A)

DE = Segment(D, E)
EF = Segment(E, F)
FD = Segment(F, D)

AD = Segment(A, D)
DB = Segment(D, B)
BE = Segment(B, E)
EC = Segment(E, C)
CF = Segment(C, F)
FA = Segment(F, A)

style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(D, E, F, label_visible=True, fill="color.accent", size_px="point_size.bold")

style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(DE, EF, FD, stroke="color.accent", stroke_width_px="line_width.bold")

style(AD, DB, stroke="color.aux", stroke_width_px=0, tick_count=1)
style(BE, EC, stroke="color.aux", stroke_width_px=0, tick_count=2)
style(CF, FA, stroke="color.aux", stroke_width_px=0, tick_count=3)
