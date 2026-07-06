A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)

triangle, AB, BC, CA = Polygon(A, B, C)
style(triangle, stroke="color.main", stroke_width_px="line_width.main", fill_opacity=0.1)
style(A, B, C, label_visible=True)

ext_AB, AB1, B1A, AA1, A1 = Polygon(B, A, 3)
ext_BC, BC1, C1B, BB1, B1 = Polygon(C, B, 3)
ext_CA, CA1, A1C, CC1, C1 = Polygon(A, C, 3)

style(ext_AB, ext_BC, ext_CA, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.05)
style(A1, B1, C1, label_visible=True, fill="color.aux", size_px="point_size.aux")

AA1_seg = Segment(A, A1)
BB1_seg = Segment(B, B1)
CC1_seg = Segment(C, C1)
style(AA1_seg, BB1_seg, CC1_seg, stroke="color.accent", stroke_width_px="line_width.bold")

F = Intersect(AA1_seg, BB1_seg)
style(F, label_visible=True, fill="color.accent", size_px="point_size.bold")

hide(ext_AB, ext_BC, ext_CA)
