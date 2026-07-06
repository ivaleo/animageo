A = Point(-3, 0)
C = Point(-1, 0)
B = Point(3, 0)

outer = Semicircle(A, B)
left = Semicircle(A, C)
right = Semicircle(C, B)
AB = Segment(A, B)
AC = Segment(A, C)
CB = Segment(C, B)

diameter = 6.0
base_x = -3.0
base_y = 0.0
ratio = 1.0 / 3.0

for n in range(1, 3):
    denom = n * n * (1 - ratio) * (1 - ratio) + ratio
    r = diameter * ((1 - ratio) * ratio) / (2 * denom)
    x = base_x + diameter * (ratio * (1 + ratio)) / (2 * denom)
    y = base_y + 2 * n * r
    O_n = Point(x, y, name=f"O{n}")
    k_n = Circle(O_n, r, name=f"k{n}")
    style(O_n, label_visible=True, label_text=f"$O_{n}$", fill="color.accent", size_px="point_size.aux")
    style(k_n, stroke="color.accent", stroke_width_px="line_width.bold")

style(A, B, C, label_visible=True)
style(outer, left, right, stroke="color.aux", stroke_width_px="line_width.bold")
style(AB, stroke="color.strong", stroke_width_px="line_width.aux")
style(AC, CB, stroke="color.aux", stroke_width_px="line_width.aux")
