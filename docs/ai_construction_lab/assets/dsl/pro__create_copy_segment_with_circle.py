A = Point(0, 0)
B = Point(2, 1)
P = Point(-1, 2)
Q = Point(1, 3)

AB = Segment(A, B)
ray_PQ = Ray(P, Q)

circle_P_AB = Circle(P, AB)
X = Intersect(circle_P_AB, ray_PQ)
PX = Segment(P, X)

style(AB, PX, stroke="color.accent", stroke_width_px="line_width.bold")
style(AB, PX, tick_count=1)

style(A, B, P, Q, X, label_visible=True)
hide(circle_P_AB, ray_PQ)
