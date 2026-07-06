# Arbelos: three semicircles on the same diameter
# Free points define the diameter endpoints and the inner division point
A = Point(-3, 0)
B = Point(3, 0)
C = Point(1, 0)  # division point on AB

# Diameter segment (hidden, used only for construction)
AB = Segment(A, B)
hide(AB)

# Midpoints for the three semicircles
O_AB = Midpoint(A, B)
O_AC = Midpoint(A, C)
O_CB = Midpoint(C, B)

# Semicircles (upper half)
semi_AB = Semicircle(O_AB, B)  # from B to A through upper half
semi_AC = Semicircle(O_AC, C)  # from C to A through upper half
semi_CB = Semicircle(O_CB, B)  # from B to C through upper half

# Style: main arbelos in accent, keep construction points minimal
style(semi_AB, semi_AC, semi_CB, stroke="color.accent", stroke_width_px="line_width.bold")
style(A, B, C, label_visible=True, fill="color.main", size_px="point_size.main")
hide(O_AB, O_AC, O_CB)
