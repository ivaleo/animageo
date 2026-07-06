O = Point(0, 0)
A = Point(-2.0, -0.8)
B = Point(-0.4, -1.2)
C = Point(-1.3, 0.9)
tri, AB, BC, CA = Polygon(A, B, C)
k = 1.6
A_h = O + (A - O) * k
B_h = O + (B - O) * k
C_h = O + (C - O) * k
tri_h, A1B1, B1C1, C1A1 = Polygon(A_h, B_h, C_h)
ray_A = Ray(O, A_h)
ray_B = Ray(O, B_h)
ray_C = Ray(O, C_h)

hide(ray_A, ray_B, ray_C)
style(O, A, B, C, A_h, B_h, C_h, label_visible=True)
style(A_h, label_text="$A'$")
style(B_h, label_text="$B'$")
style(C_h, label_text="$C'$")
style(tri_h, fill="color.accent", fill_opacity=0.12)
style(A1B1, B1C1, C1A1, stroke="color.accent", stroke_width_px="line_width.bold")
