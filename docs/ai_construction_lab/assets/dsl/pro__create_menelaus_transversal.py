# Triangle ABC
A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")

# Point D on AB
D = A + 0.4 * (B - A)
style(D, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Point F on extension of BC beyond C
k = 0.6
F = C + k * (C - B)
CF = Segment(C, F)
style(CF, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")
style(F, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Transversal line through D and F
transversal = Line(D, F)

# Point E as intersection of transversal with AC
E = Intersect(transversal, CA)
style(E, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Draw transversal segments
DE = Segment(D, E)
EF = Segment(E, F)
style(DE, EF, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide infinite transversal line
hide(transversal)
