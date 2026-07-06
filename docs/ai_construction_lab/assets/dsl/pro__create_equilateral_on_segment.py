A = Point(-2, 0)
B = Point(2, 0)

tri, AB, BC, CA, C = Polygon(A, B, 3)

style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")

style(AB, BC, CA, tick_count=1)

ang1 = Angle(B, A, C)
ang2 = Angle(C, B, A)
ang3 = Angle(A, C, B)
style(ang1, ang2, ang3, arc_size_px="angle_radius.main", tick_count=1)
