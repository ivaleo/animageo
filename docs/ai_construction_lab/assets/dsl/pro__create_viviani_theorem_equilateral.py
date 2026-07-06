A = Point(-3, -1)
B = Point(3, -1)
tri, AB, BC, CA, C = Polygon(A, B, 3)
P = Point(0, 0.5)

# Perpendiculars from P to each side
perp_AB = PerpendicularLine(P, AB)
perp_BC = PerpendicularLine(P, BC)
perp_CA = PerpendicularLine(P, CA)

# Feet of perpendiculars
F_AB = Intersect(perp_AB, AB)
F_BC = Intersect(perp_BC, BC)
F_CA = Intersect(perp_CA, CA)

# Visible perpendicular segments
PF_AB = Segment(P, F_AB)
PF_BC = Segment(P, F_BC)
PF_CA = Segment(P, F_CA)

# Right angle markers at feet
ang_AB = Angle(A, F_AB, P)
ang_BC = Angle(B, F_BC, P)
ang_CA = Angle(C, F_CA, P)

# Styling
style(tri, fill="color.aux", fill_opacity=0.1)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(F_AB, F_BC, F_CA, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(PF_AB, PF_BC, PF_CA, stroke="color.accent", stroke_width_px="line_width.bold")
style(ang_AB, ang_BC, ang_CA, right_angle_marker=True, right_angle_size_px="angle_radius.right")
hide(perp_AB, perp_BC, perp_CA)
