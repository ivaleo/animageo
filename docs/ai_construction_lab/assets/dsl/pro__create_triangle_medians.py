A = Point(0, 0)
B = Point(4, 0)
tri, AB, BC, CA, C = Polygon(A, B, 3)
style(tri, fill_opacity=0.1, stroke="color.main", stroke_width_px="line_width.main")
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

D = Midpoint(B, C)
E = Midpoint(C, A)
F = Midpoint(A, B)

med_AD = Segment(A, D)
med_BE = Segment(B, E)
med_CF = Segment(C, F)
style(med_AD, med_BE, med_CF, stroke="color.accent", stroke_width_px="line_width.bold")

G = Intersect(med_AD, med_BE)
style(G, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="G")

style(D, E, F, fill="color.aux", size_px="point_size.aux", label_visible=False)

BD = Segment(B, D)
DC = Segment(D, C)
CE = Segment(C, E)
EA = Segment(E, A)
AF = Segment(A, F)
FB = Segment(F, B)
style(BD, DC, CE, EA, AF, FB, stroke_width_px=0, tick_count=1)
