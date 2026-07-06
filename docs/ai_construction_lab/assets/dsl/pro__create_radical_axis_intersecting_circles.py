O1 = Point(-2, 0)
O2 = Point(2, 0)
circle1 = Circle(O1, 2.5)
circle2 = Circle(O2, 2.5)

P1, P2 = Intersect(circle1, circle2)
radical_axis = Line(P1, P2)
center_line = Segment(O1, O2)

style(circle1, circle2, stroke="color.main", stroke_width_px="line_width.main")
style(O1, O2, fill="color.main", size_px="point_size.main", label_visible=True)
style(P1, P2, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(radical_axis, stroke="color.accent", stroke_width_px="line_width.bold")
style(center_line, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4,4")
