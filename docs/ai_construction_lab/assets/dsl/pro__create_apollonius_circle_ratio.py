A = Point(-2, 0)
B = Point(2, 0)

# Internal division point C on AB such that AC:CB = 2:1
C = A + (2.0 / 3.0) * (B - A)

# External division point D on line AB such that AD:DB = 2:1 (externally)
D = A + 2.0 * (B - A)

# Apollonius circle has CD as diameter
O = Midpoint(C, D)
circle = Circle(O, C)

# Sample point P on the circle
P = Rotate(C, pi / 3, O)

# Draw segments PA and PB
PA = Segment(P, A)
PB = Segment(P, B)

# Mark the ratio with labels
style(PA, stroke="color.accent", stroke_width_px="line_width.bold")
style(PB, stroke="color.accent", stroke_width_px="line_width.bold")
style(PA, label_text="$2x$", label_visible=True)
style(PB, label_text="$x$", label_visible=True)

# Style the circle and diameter
style(circle, stroke="color.main", stroke_width_px="line_width.main")
CD = Segment(C, D)
style(CD, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")

# Style points
style(A, B, label_visible=True, fill="color.strong", size_px="point_size.bold")
style(C, D, label_visible=True, fill="color.aux", size_px="point_size.aux")
style(O, label_visible=True, fill="color.aux", size_px="point_size.aux")
style(P, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Hide helper objects if needed (none here)
