f = Function("y = 0.35*x^2 - 1.2")
g = Function("y = 0.35*x + 0.2")
P, Q = Intersect(f, g)
secant = Segment(P, Q)

style(P, Q, label_visible=True)
style(secant, stroke="color.accent", stroke_width_px="line_width.bold")
