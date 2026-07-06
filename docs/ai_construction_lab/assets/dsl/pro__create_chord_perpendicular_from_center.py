# Given circle with center O and point A on it
O = Point(0, 0)
A = Point(3, 0)
circle = Circle(O, A)

# Construct point B on the same circle by rotating A around O
B = Rotate(A, 2.2, O)  # angle ~126°, generic non-degenerate position

# Chord AB
AB = Segment(A, B)

# Perpendicular from O to chord AB
perp_line = PerpendicularLine(O, AB)
H = Intersect(perp_line, AB)
OH = Segment(O, H)

# Mark right angle at H
right_angle = Angle(A, H, O)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Show that H is the midpoint: mark equal halves AH and HB
AH = Segment(A, H)
HB = Segment(H, B)
style(AH, HB, stroke="color.accent", stroke_width_px="line_width.bold", tick_count=1)

# Style main objects
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(AB, stroke="color.main", stroke_width_px="line_width.main")
style(OH, stroke="color.aux", stroke_width_px="line_width.aux")
style(O, A, B, H, label_visible=True)
style(H, fill="color.accent", size_px="point_size.bold")

# Hide construction helpers
hide(perp_line)
