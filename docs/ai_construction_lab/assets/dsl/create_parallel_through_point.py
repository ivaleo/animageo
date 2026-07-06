A = Point(-3.2, -1.2)
B = Point(2.8, 0.0)
P = Point(-1.2, 2.0)
base = Line(A, B)
parallel = Line(P, base)

style(A, B, P, label_visible=True)
style(base, stroke="color.strong", stroke_width_px="line_width.main")
style(parallel, stroke="color.accent", stroke_width_px="line_width.bold")
