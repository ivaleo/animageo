f = Function("y = sin(x)")
O = Point(0, 0)
c = Circle(O, 2.0)
P, Q, R, S = Intersect(f, c)

style(O, P, Q, R, S, label_visible=True)
style(f, stroke="color.strong", stroke_width_px="line_width.main")
style(c, stroke="color.aux", stroke_width_px="line_width.main")
style(P, Q, R, S, fill="color.accent", size_px="point_size.bold")
