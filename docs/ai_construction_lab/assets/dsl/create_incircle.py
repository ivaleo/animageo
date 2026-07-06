A = Point(-3.2, -2)
B = Point(3.1, -1.7)
C = Point(-0.7, 2.3)

tri, AB, BC, CA = Polygon(A, B, C)
incircle = Incircle(A, B, C)
I = Center(incircle)

style(A, B, C, I, label_visible=True)
style(incircle, stroke="color.accent", stroke_width_px="line_width.bold")
style(I, fill="color.accent", size_px="point_size.bold")
