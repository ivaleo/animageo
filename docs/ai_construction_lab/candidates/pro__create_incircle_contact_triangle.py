# Triangle ABC
A = Point(-3, -1)
B = Point(4, -2)
C = Point(1, 4)

# Triangle sides as explicit segments for clarity
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Incenter via incircle
inc = Incircle(A, B, C)
I = Center(inc)

# Touchpoints: perpendiculars from incenter to each side
# Side AB
perp_AB = PerpendicularLine(I, AB)
D = Intersect(perp_AB, AB)
# Side BC
perp_BC = PerpendicularLine(I, BC)
E = Intersect(perp_BC, BC)
# Side CA
perp_CA = PerpendicularLine(I, CA)
F = Intersect(perp_CA, CA)

# Hide construction helpers
hide(perp_AB, perp_BC, perp_CA)

# Style: triangle sides
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Style: incircle
style(inc, stroke="color.accent", stroke_width_px="line_width.bold", fill_opacity=0.1)

# Style: incenter and touchpoints
style(I, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(D, E, F, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Right-angle markers at touchpoints
# At D on AB
ang_D = Angle(A, D, I)
style(ang_D, right_angle_marker=True, right_angle_size_px="angle_radius.right")
# At E on BC
ang_E = Angle(B, E, I)
style(ang_E, right_angle_marker=True, right_angle_size_px="angle_radius.right")
# At F on CA
ang_F = Angle(C, F, I)
style(ang_F, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Labels for vertices
style(A, B, C, label_visible=True)
