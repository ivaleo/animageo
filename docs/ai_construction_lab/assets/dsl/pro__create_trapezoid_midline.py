# Trapezoid ABCD with midsegment (average of bases)
A = Point(-4, 0)
B = Point(4, 0)
C = Point(2, 3)
D = Point(-2, 3)

# Sides
AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Midpoints of non-parallel sides
M_BC = Midpoint(B, C)
M_AD = Midpoint(A, D)

# Midsegment
midsegment = Segment(M_BC, M_AD)

# Mark equal halves on BC
BM = Segment(B, M_BC)
MC = Segment(M_BC, C)
style(BM, MC, stroke_width_px=0, tick_count=1)

# Mark equal halves on AD
AM = Segment(A, M_AD)
MD = Segment(M_AD, D)
style(AM, MD, stroke_width_px=0, tick_count=2)

# Style main figure
style(AB, CD, stroke="color.main", stroke_width_px="line_width.main")
style(BC, DA, stroke="color.main", stroke_width_px="line_width.main")
style(midsegment, stroke="color.accent", stroke_width_px="line_width.bold")
style(M_BC, M_AD, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(A, B, C, D, label_visible=True)
