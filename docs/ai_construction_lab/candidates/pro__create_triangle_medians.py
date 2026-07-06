A = Point(0, 0)
B = Point(4, 0)
tri, AB, BC, CA, C = Polygon(A, B, 3)

M_AB = Midpoint(A, B)
M_BC = Midpoint(B, C)
M_CA = Midpoint(C, A)

med_CC = Segment(C, M_AB)
med_AA = Segment(A, M_BC)
med_BB = Segment(B, M_CA)

G = Intersect(med_AA, med_BB)

style(tri, stroke="color.main", stroke_width_px="line_width.main")
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(med_AA, med_BB, med_CC, stroke="color.accent", stroke_width_px="line_width.bold")
style(M_AB, M_BC, M_CA, fill="color.aux", size_px="point_size.aux", label_visible=False)
style(G, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="G")
