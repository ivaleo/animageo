A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
tri, AB, BC, CA = Polygon(A, B, C)
t = 0.4
D = A + (B - A) * t
P = D + (C - B)
L = Line(D, P)
E = Intersect(L, Line(A, C))
DE = Segment(D, E)
hide(P, L)
style(A, B, C, D, E, label_visible=True)
