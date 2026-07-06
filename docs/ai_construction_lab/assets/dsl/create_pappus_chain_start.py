A = Point(-3.0, -1.0)
B = Point(3.0, -1.0)
C = Point(-0.9, -1.0)
outer = Semicircle(A, B)
left = Semicircle(A, C)
right = Semicircle(C, B)
AB = Segment(A, B)

outer_r = 3.0
left_r = 1.05
right_r = 1.95
for n in range(1, 3):
    r = left_r * right_r * (outer_r - left_r) / ((left_r + right_r) ** 2 * n * n + (outer_r - left_r) ** 2)
    x = -0.9 + (right_r - left_r) * n * n / 2.0
    y = -1.0 + 2 * n * r
    O_n = Point(x, y, name=f"O{n}")
    k_n = Circle(O_n, r, name=f"k{n}")
    style(O_n, label_visible=True, label_text=f"$O_{n}$", fill="color.accent", size_px="point_size.aux")
    style(k_n, stroke="color.accent", stroke_width_px="line_width.bold")

style(A, B, C, label_visible=True)
style(outer, left, right, stroke="color.aux", stroke_width_px="line_width.bold")
style(AB, stroke="color.strong", stroke_width_px="line_width.aux")
