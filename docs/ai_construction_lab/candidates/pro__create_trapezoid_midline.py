A = Point(-4, 0)
B = Point(4, 0)
C = Point(2, 3)
D = Point(-2, 3)

AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

M = Midpoint(A, D)
N = Midpoint(B, C)
MN = Segment(M, N)

style(AB, CD, stroke="color.main", stroke_width_px="line_width.main")
style(BC, DA, stroke="color.aux", stroke_width_px="line_width.aux")
style(MN, stroke="color.accent", stroke_width_px="line_width.bold")
style(M, N, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(A, B, C, D, label_visible=True)
