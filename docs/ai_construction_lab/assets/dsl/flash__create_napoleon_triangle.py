A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 2)
style(A, B, C, label_visible=True)

# External equilateral triangles on each side
# On side AB: use Polygon(B, A, 3) to get external vertex opposite C
tri_AB, AB_side, BA_side, AB_third, C1 = Polygon(B, A, 3)
# On side BC: use Polygon(C, B, 3) to get external vertex opposite A
tri_BC, BC_side, CB_side, BC_third, A1 = Polygon(C, B, 3)
# On side CA: use Polygon(A, C, 3) to get external vertex opposite B
tri_CA, CA_side, AC_side, CA_third, B1 = Polygon(A, C, 3)

# Style external triangles with light fill
style(tri_AB, tri_BC, tri_CA, fill="color.aux", fill_opacity=0.15, stroke="color.aux", stroke_width_px="line_width.aux")

# Hide redundant sides from polygons (keep only the outer sides visible)
hide(AB_side, BA_side, BC_side, CB_side, CA_side, AC_side)

# Draw the original triangle sides explicitly
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Napoleon triangle: connect centers of external equilateral triangles
# Use centroids of the equilateral triangles
G1 = Centroid(tri_AB)
G2 = Centroid(tri_BC)
G3 = Centroid(tri_CA)

# Napoleon triangle
napoleon, G1G2, G2G3, G3G1 = Polygon(G1, G2, G3)
style(napoleon, fill="color.accent", fill_opacity=0.2, stroke="color.accent", stroke_width_px="line_width.bold")
style(G1, G2, G3, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Mark equal sides of external triangles (optional, but good for clarity)
# Each external triangle has all sides equal; we can mark one side per triangle
style(AB_third, BC_third, CA_third, stroke="color.aux", stroke_width_px="line_width.aux", tick_count=1)
