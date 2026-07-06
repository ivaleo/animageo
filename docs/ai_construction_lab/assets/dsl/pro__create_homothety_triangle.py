# Free points for the triangle and homothety center
A = Point(-2, 1)
B = Point(1, 2)
C = Point(0, -1)
O = Point(0, 0)

# Original triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Homothety with center O and factor 1.6 using vector arithmetic
A1 = O + 1.6 * (A - O)
B1 = O + 1.6 * (B - O)
C1 = O + 1.6 * (C - O)

# Image triangle sides
A1B1 = Segment(A1, B1)
B1C1 = Segment(B1, C1)
C1A1 = Segment(C1, A1)

# Style original triangle as main
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, fill="color.main", size_px="point_size.main", label_visible=True)

# Style image triangle as accent
style(A1B1, B1C1, C1A1, stroke="color.accent", stroke_width_px="line_width.bold")
style(A1, B1, C1, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(A1, label_text="$A'$")
style(B1, label_text="$B'$")
style(C1, label_text="$C'$")

# Style center
style(O, fill="color.aux", size_px="point_size.bold", label_visible=True)

# Show correspondence lines as auxiliary
OA1 = Segment(O, A1)
OB1 = Segment(O, B1)
OC1 = Segment(O, C1)
style(OA1, OB1, OC1, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")
