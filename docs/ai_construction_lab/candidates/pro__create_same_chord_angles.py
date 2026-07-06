# Given points for the circle and chord
O = Point(0, 0)
A = Point(-2.1, 1.7)
B = Point(2.1, 1.7)

# Circle with center O through A (and B)
circle = Circle(O, A)

# Chord AB
chord = Segment(A, B)

# Two distinct points on the circle for inscribed angles
C = Rotate(A, 2 * pi / 3, O)
D = Rotate(A, -2 * pi / 3, O)

# Inscribed angles
angle_ACB = Angle(A, C, B)
angle_ADB = Angle(A, D, B)

# Style
style(circle, chord, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, D, label_visible=True, fill="color.main", size_px="point_size.main")
style(angle_ACB, angle_ADB, arc_size_px="angle_radius.main", tick_count=1)

# Hide center O
hide(O)
