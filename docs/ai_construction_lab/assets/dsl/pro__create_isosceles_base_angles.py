# Isosceles triangle ABC with AB = AC
# Construct equal sides by dependency: B and C lie on the same circle centered at A
A = Point(0, 0)
B = Point(2, 0)
circle_A = Circle(A, B)
# Choose C on the circle, not collinear with A and B
C = Rotate(B, 2 * pi / 3, A)

# Triangle sides
AB = Segment(A, B)
AC = Segment(A, C)
BC = Segment(B, C)

# Mark equal sides with matching tick_count
style(AB, AC, stroke="color.main", stroke_width_px="line_width.main", tick_count=1)
style(BC, stroke="color.main", stroke_width_px="line_width.main")

# Base angles
angle_B = Angle(A, B, C)
angle_C = Angle(B, C, A)
style(angle_B, angle_C, arc_size_px="angle_radius.main", tick_count=1)

# Vertex labels
style(A, B, C, label_visible=True)

# Hide construction helpers
hide(circle_A)
