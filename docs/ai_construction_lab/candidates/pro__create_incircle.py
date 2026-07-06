A = Point(2, 4)
B = Point(-3, -1)
C = Point(4, -2)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

inc = Incircle(A, B, C)
I = Center(inc)

style(A, B, C, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(inc, stroke="color.accent", stroke_width_px="line_width.bold")
style(I, label_visible=True, fill="color.accent", size_px="point_size.bold")
