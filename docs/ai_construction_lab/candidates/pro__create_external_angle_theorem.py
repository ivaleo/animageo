A = Point(-3, 1)
B = Point(1, -2)
C = Point(2, 3)

AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")

ray_BC = Ray(B, C)
ray_AC = Ray(A, C)

style(ray_BC, ray_AC, stroke="color.aux", stroke_width_px="line_width.aux")

ext_angle = Angle(ray_BC, ray_AC)
style(ext_angle, stroke="color.accent", stroke_width_px="line_width.bold", arc_size_px="angle_radius.bold", tick_count=1)

int_angle_A = Angle(CA, AB)
int_angle_B = Angle(AB, BC)

style(int_angle_A, int_angle_B, stroke="color.accent", stroke_width_px="line_width.bold", arc_size_px="angle_radius.bold", tick_count=1)

hide(ray_BC, ray_AC)
