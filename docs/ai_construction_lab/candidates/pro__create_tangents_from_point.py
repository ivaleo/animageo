O = Point(0, 0)
circle = Circle(O, 3)
P = Point(5, 2)

t1, t2 = Tangent(P, circle)
T1 = Intersect(t1, circle)
T2 = Intersect(t2, circle)

PT1 = Segment(P, T1)
PT2 = Segment(P, T2)

hide(t1, t2)

style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(O, fill="color.main", size_px="point_size.main", label_visible=True)
style(P, fill="color.main", size_px="point_size.main", label_visible=True)
style(T1, T2, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(PT1, PT2, stroke="color.accent", stroke_width_px="line_width.bold")

right_angle1 = Angle(P, T1, O)
right_angle2 = Angle(P, T2, O)
style(right_angle1, right_angle2, right_angle_marker=True, right_angle_size_px="angle_radius.right")
