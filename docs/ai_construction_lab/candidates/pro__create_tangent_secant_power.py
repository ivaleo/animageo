O = Point(0, 0)
circle = Circle(O, 2)

P = Point(-3, 1)

t1, t2 = Tangent(P, circle)
T = Intersect(t1, circle)
PT = Segment(P, T)

secant_line = Line(P, Point(-1, 2))
A, B = Intersect(secant_line, circle)
PA = Segment(P, A)
PB = Segment(P, B)

hide(t1, t2, secant_line)

style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(PT, stroke="color.accent", stroke_width_px="line_width.bold")
style(PA, PB, stroke="color.aux", stroke_width_px="line_width.aux")
style(P, T, A, B, label_visible=True, fill="color.main", size_px="point_size.main")
style(O, label_visible=False, fill="color.aux", size_px="point_size.aux")

OT = Segment(O, T)
style(OT, stroke="color.aux", stroke_width_px="line_width.aux")
right_angle = Angle(P, T, O)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")
