# Triangle with midsegment connecting midpoints of two sides
A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 5)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

D = Midpoint(A, B)
E = Midpoint(A, C)
DE = Segment(D, E)
style(DE, stroke="color.accent", stroke_width_px="line_width.bold")
style(D, E, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Mark equal halves on AB and AC to show midpoints
AD = Segment(A, D)
DB = Segment(D, B)
AE = Segment(A, E)
EC = Segment(E, C)
style(AD, DB, stroke_width_px=0, tick_count=1)
style(AE, EC, stroke_width_px=0, tick_count=2)

# Highlight the side parallel to the midsegment (BC)
style(BC, stroke="color.accent", stroke_width_px="line_width.bold")
