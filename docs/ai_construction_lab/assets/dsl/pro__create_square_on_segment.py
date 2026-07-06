# Given segment AB
A = Point(0, 0)
B = Point(2, 0)
AB = Segment(A, B)

# Construct square ABCD on AB
# Rotate B around A by 90 degrees to get D
D = Rotate(B, pi/2, A)
# Rotate A around B by -90 degrees to get C
C = Rotate(A, -pi/2, B)

# Sides of the square
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Style the square sides
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")

# Mark right angles at all four vertices
right_A = Angle(D, A, B)
right_B = Angle(A, B, C)
right_C = Angle(B, C, D)
right_D = Angle(C, D, A)
style(right_A, right_B, right_C, right_D, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Mark equal sides with matching tick_count
style(AB, BC, CD, DA, tick_count=1)

# Label vertices
style(A, B, C, D, label_visible=True)
