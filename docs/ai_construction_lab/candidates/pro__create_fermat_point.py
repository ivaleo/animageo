# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)
style(A, B, C, label_visible=True)

# Sides of ABC
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# External equilateral triangles on each side
# On AB (external, opposite C)
C_AB = Rotate(B, pi/3, A)  # rotate B around A by +60°
tri_AB, _, _, _ = Polygon(A, B, C_AB)
style(tri_AB, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.1)

# On BC (external, opposite A)
A_BC = Rotate(C, pi/3, B)
tri_BC, _, _, _ = Polygon(B, C, A_BC)
style(tri_BC, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.1)

# On CA (external, opposite B)
B_CA = Rotate(A, pi/3, C)
tri_CA, _, _, _ = Polygon(C, A, B_CA)
style(tri_CA, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.1)

# Lines connecting vertices of ABC to opposite vertices of external triangles
AA_BC = Line(A, A_BC)
BB_CA = Line(B, B_CA)
CC_AB = Line(C, C_AB)
style(AA_BC, BB_CA, CC_AB, stroke="color.accent", stroke_width_px="line_width.bold")

# Fermat point is intersection of these lines
F = Intersect(AA_BC, BB_CA)
style(F, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="F")

# Hide auxiliary lines and triangle borders if desired, but keep Fermat point visible
hide(AA_BC, BB_CA, CC_AB)
