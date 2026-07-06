# Given circle with center O and chord AB
O = Point(0, 0)
A = Point(-2.1, 1.7)
circle = Circle(O, A)
B = Rotate(A, 2.3, O)  # ensures B lies on the circle

# Chord AB
AB = Segment(A, B)

# Perpendicular from O to chord AB
perp_line = PerpendicularLine(O, AB)
H = Intersect(perp_line, AB)

# Show that H is the midpoint: mark equal halves
AH = Segment(A, H)
HB = Segment(H, B)
style(AH, HB, stroke="color.accent", stroke_width_px="line_width.bold", tick_count=1)

# Right angle at H
right_angle = Angle(A, H, O)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Style main objects
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(AB, stroke="color.main", stroke_width_px="line_width.main")
style(O, fill="color.main", size_px="point_size.main", label_visible=True)
style(A, B, fill="color.main", size_px="point_size.main", label_visible=True)
style(H, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Hide construction helpers
hide(perp_line)
