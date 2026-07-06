A = Point(-2.8, -1.4)
B = Point(2.8, -1.4)
C = Rotate(B, pi / 3, A)
tri, AB, BC, CA = Polygon(A, B, C)

style(A, B, C, label_visible=True)
style(AB, BC, CA, tick_count=1)
