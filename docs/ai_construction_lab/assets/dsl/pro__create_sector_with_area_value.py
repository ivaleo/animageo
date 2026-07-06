O = Point(0, 0)
A = Point(3, 0)
B = Rotate(A, 2 * pi / 3, O)

circle = Circle(O, A)
sector = CircleSector(O, A, B)
OA = Segment(O, A)
OB = Segment(O, B)
central_angle = Angle(A, O, B)

style(sector, stroke="color.accent", stroke_width_px="line_width.bold", fill="color.accent")
style(OA, OB, stroke="color.accent", stroke_width_px="line_width.bold")
style(central_angle, arc_size_px="angle_radius.bold", tick_count=1, label_visible=True, label_text="$120^\\circ$")
style(O, A, B, label_visible=True, fill="color.accent", size_px="point_size.bold")
