# Given circle with center O and point A on it
O = Point(0, 0)
A = Point(2, 0)
circle = Circle(O, A)

# Construct B on the circle by rotating A around O by 120 degrees
B = Rotate(A, 2 * pi / 3, O)

# Chord AB
AB = Segment(A, B)

# Choose two distinct points C and D on the circle, not equal to A or B
C = Rotate(A, pi / 3, O)
D = Rotate(A, -pi / 4, O)

# Inscribed angles ACB and ADB
angle_ACB = Angle(A, C, B)
angle_ADB = Angle(A, D, B)

# Style the construction
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(AB, stroke="color.accent", stroke_width_px="line_width.bold")
style(A, B, C, D, label_visible=True, fill="color.main", size_px="point_size.main")
style(angle_ACB, angle_ADB, arc_size_px="angle_radius.main", tick_count=1)
