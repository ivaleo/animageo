A = Point(0, 0)
B = Point(4, 0)
C = Point(1, 3)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True)

t = 0.4
D = A + t * (B - A)
E = A + t * (C - A)
DE = Segment(D, E)
style(DE, stroke="color.accent", stroke_width_px="line_width.bold")
style(D, E, label_visible=True, fill="color.accent", size_px="point_size.bold")

style(BC, stroke="color.accent", stroke_width_px="line_width.bold")
