A = Point(-2.8, -0.8)
B = Point(-1.0, 1.5)
C = Point(1.1, 1.3)
D = Point(2.7, -0.5)
E = Point(0.4, -1.7)
conic = Conic(A, B, C, D, E)

style(A, B, C, D, E, label_visible=True)
style(conic, stroke="color.accent", stroke_width_px="line_width.bold")
