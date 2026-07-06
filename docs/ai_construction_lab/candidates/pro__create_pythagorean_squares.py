# Right triangle with squares on sides for Pythagorean theorem
# Free points A, B, C define the right triangle with right angle at C
A = Point(0, 0)
B = Point(4, 0)
C = Point(0, 3)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Right angle mark at C
right_angle = Angle(A, C, B)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Square on AB (hypotenuse) - outward
# Rotate A around B by -90° to get D, then B around A by 90° to get E
D = Rotate(A, -pi/2, B)
E = Rotate(B, pi/2, A)
# Complete square: F = D + (E - A)
F = D + (E - A)
sq_AB, s1, s2, s3, s4 = Polygon(A, B, D, F)
# Hide the polygon boundary, we'll draw explicit segments for clarity
hide(sq_AB)
AB_sq1 = Segment(A, B)
AB_sq2 = Segment(B, D)
AB_sq3 = Segment(D, F)
AB_sq4 = Segment(F, A)
style(AB_sq1, AB_sq2, AB_sq3, AB_sq4, stroke="color.accent", stroke_width_px="line_width.bold")

# Square on BC (leg) - outward
# Rotate B around C by 90° to get G, then C around B by -90° to get H
G = Rotate(B, pi/2, C)
H = Rotate(C, -pi/2, B)
# Complete square: I = G + (H - B)
I = G + (H - B)
sq_BC, t1, t2, t3, t4 = Polygon(B, C, G, I)
hide(sq_BC)
BC_sq1 = Segment(B, C)
BC_sq2 = Segment(C, G)
BC_sq3 = Segment(G, I)
BC_sq4 = Segment(I, B)
style(BC_sq1, BC_sq2, BC_sq3, BC_sq4, stroke="color.aux", stroke_width_px="line_width.aux")

# Square on CA (leg) - outward
# Rotate C around A by -90° to get J, then A around C by 90° to get K
J = Rotate(C, -pi/2, A)
K = Rotate(A, pi/2, C)
# Complete square: L = J + (K - C)
L = J + (K - C)
sq_CA, u1, u2, u3, u4 = Polygon(C, A, J, L)
hide(sq_CA)
CA_sq1 = Segment(C, A)
CA_sq2 = Segment(A, J)
CA_sq3 = Segment(J, L)
CA_sq4 = Segment(L, C)
style(CA_sq1, CA_sq2, CA_sq3, CA_sq4, stroke="color.aux", stroke_width_px="line_width.aux")

# Style triangle sides
style(AB, stroke="color.accent", stroke_width_px="line_width.bold")
style(BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Labels
style(A, B, C, label_visible=True)
style(A, label_text="A")
style(B, label_text="B")
style(C, label_text="C")

# Optional: add area labels
# We'll attach a label to the hypotenuse square showing c^2
# For simplicity, we'll just show the figure.
