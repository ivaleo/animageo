A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
style(A, B, C, label_visible=True)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

D = Midpoint(A, B)
E = Midpoint(B, C)
F = Midpoint(C, A)

DE = Segment(D, E)
EF = Segment(E, F)
FD = Segment(F, D)

style(D, E, F, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(DE, EF, FD, stroke="color.accent", stroke_width_px="line_width.bold")

AD = Segment(A, D)
DB = Segment(D, B)
BE = Segment(B, E)
EC = Segment(E, C)
CF = Segment(C, F)
FA = Segment(F, A)

style(AD, DB, tick_count=1, stroke_width_px=0)
style(BE, EC, tick_count=2, stroke_width_px=0)
style(CF, FA, tick_count=3, stroke_width_px=0)
