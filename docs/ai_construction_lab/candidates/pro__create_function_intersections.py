# Parabola and line with intersection points and connecting segment

parabola = Function("0.35*x^2 - 1.2")
line = Function("0.35*x + 0.2")

P1, P2 = Intersect(parabola, line)

chord = Segment(P1, P2)

style(parabola, stroke="color.main", stroke_width_px="line_width.main")
style(line, stroke="color.main", stroke_width_px="line_width.main")
style(P1, P2, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(chord, stroke="color.accent", stroke_width_px="line_width.bold")
