# Right triangle with circumcenter at midpoint of hypotenuse
A = Point(0, 0)
B = Point(6, 0)
C = Point(0, 4)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Right angle at A
right_angle = Angle(B, A, C)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Hypotenuse BC
style(BC, stroke="color.accent", stroke_width_px="line_width.bold")

# Midpoint of hypotenuse
M = Midpoint(B, C)
style(M, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Circumcenter is M
# Circumcircle
circ = Circle(M, B)
style(circ, stroke="color.aux", stroke_width_px="line_width.aux")

# Show that M is equidistant from vertices (optional radii)
MB = Segment(M, B)
MC = Segment(M, C)
MA = Segment(M, A)
style(MB, MC, MA, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 2")

# Labels
style(A, B, C, label_visible=True)
style(M, label_text="$M$")
