O = Point(0, 0)
circle = Circle(O, 3)
P = Point(6, 2)

t1, t2 = Tangent(P, circle)
T1 = Intersect(t1, circle)
T2 = Intersect(t2, circle)

PT1 = Segment(P, T1)
PT2 = Segment(P, T2)
OT1 = Segment(O, T1)
OT2 = Segment(O, T2)

right_angle1 = Angle(P, T1, O)
right_angle2 = Angle(P, T2, O)

style(O, fill="color.strong", size_px="point_size.bold", label_visible=True)
style(P, fill="color.strong", size_px="point_size.bold", label_visible=True)
style(T1, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$T_1$")
style(T2, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$T_2$")

style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(PT1, PT2, stroke="color.accent", stroke_width_px="line_width.bold")
style(OT1, OT2, stroke="color.aux", stroke_width_px="line_width.aux")

style(right_angle1, right_angle2, right_angle_marker=True, right_angle_size_px="angle_radius.right")

hide(t1, t2)
