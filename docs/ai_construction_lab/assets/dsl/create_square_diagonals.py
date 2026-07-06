A = Point(-2, -2)
B = Point(2, -2)
C = Point(2, 2)
D = Point(-2, 2)

square, AB, BC, CD, DA = Polygon(A, B, C, D)
diag_AC = Segment(A, C)
diag_BD = Segment(B, D)
O = Intersect(diag_AC, diag_BD)

style(A, B, C, D, O, label_visible=True)
style(diag_AC, diag_BD, stroke="color.accent", stroke_width_px="line_width.bold")
style(O, fill="color.accent", size_px="point_size.bold")
