# Given triangle ABC
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
# On AB (external, so vertex opposite C)
tri_AB, _, _, _, C_AB = Polygon(B, A, 3)
style(tri_AB, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.1)

# On BC (external, vertex opposite A)
tri_BC, _, _, _, A_BC = Polygon(C, B, 3)
style(tri_BC, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.1)

# On CA (external, vertex opposite B)
tri_CA, _, _, _, B_CA = Polygon(A, C, 3)
style(tri_CA, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.1)

# Centers of the external equilateral triangles (centroids)
O_AB = Centroid(tri_AB)
O_BC = Centroid(tri_BC)
O_CA = Centroid(tri_CA)
style(O_AB, O_BC, O_CA, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Napoleon triangle (connecting the centers)
nap_tri, nap_AB, nap_BC, nap_CA = Polygon(O_AB, O_BC, O_CA)
style(nap_tri, stroke="color.accent", stroke_width_px="line_width.bold", fill_opacity=0.15)
style(nap_AB, nap_BC, nap_CA, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide the external triangle vertices (keep only centers)
hide(C_AB, A_BC, B_CA)

# Optional: mark the external triangles as equilateral with tick marks on their sides
# (but they are already hidden, so we skip that for cleanliness)
