A = Point(0, 0)
B = Point(3, 1)
P = Point(1, 2)
Q = Point(4, 3)

AB = Segment(A, B)
ray = Ray(P, Q)

circle = Circle(P, AB)
C = Intersect(circle, ray, index=1)
PC = Segment(P, C)

style(AB, PC, stroke="color.accent", stroke_width_px="line_width.bold")
style(AB, PC, tick_count=1)

style(A, B, P, Q, C, label_visible=True)
style(ray, stroke="color.aux", stroke_width_px="line_width.aux")
hide(circle)
