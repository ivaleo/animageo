# Right triangle with squares on sides for Pythagorean theorem
A = Point(0, 0)
B = Point(4, 0)
C = Point(0, 3)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Right angle at A
right_angle = Angle(B, A, C)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Squares on each side
# Square on AB (bottom)
sq_AB, sAB1, sAB2, sAB3, sAB4, D, E = Polygon(A, B, 4)
# Square on BC (hypotenuse, outward)
sq_BC, sBC1, sBC2, sBC3, sBC4, F, G = Polygon(B, C, 4)
# Square on CA (left side, outward)
sq_CA, sCA1, sCA2, sCA3, sCA4, H, I = Polygon(C, A, 4)

# Style triangle
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")

# Style squares with distinct fills
style(sq_AB, fill="color.accent", fill_opacity=0.2, stroke="color.accent", stroke_width_px="line_width.main")
style(sq_BC, fill="color.strong", fill_opacity=0.2, stroke="color.strong", stroke_width_px="line_width.main")
style(sq_CA, fill="color.aux", fill_opacity=0.2, stroke="color.aux", stroke_width_px="line_width.main")

# Hide square vertices not part of triangle
style(D, E, F, G, H, I, label_visible=False, size_px="point_size.aux")

# Optional: label square areas (a^2, b^2, c^2)
style(sq_AB, label_text="$a^2$", label_visible=True, font_size_px="font_size.bold")
style(sq_BC, label_text="$c^2$", label_visible=True, font_size_px="font_size.bold")
style(sq_CA, label_text="$b^2$", label_visible=True, font_size_px="font_size.bold")
