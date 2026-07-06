A = Point(-3, 1)
B = Point(-1, 4)
C = Point(2, 3)
D = Point(4, 0)
E = Point(1, -2)

conic = Conic(A, B, C, D, E)

style(A, B, C, D, E, fill="color.strong", size_px="point_size.bold", label_visible=True)
style(conic, stroke="color.accent", stroke_width_px="line_width.bold")
