A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)

# External equilateral triangles on each side
# On AB: use Polygon(B, A, 3) to place third vertex outward (assuming triangle ABC is counterclockwise)
tri_AB, AB_side, B_A, A_B, C_AB = Polygon(B, A, 3)
# On BC: use Polygon(C, B, 3)
tri_BC, BC_side, C_B, B_C, C_BC = Polygon(C, B, 3)
# On CA: use Polygon(A, C, 3)
tri_CA, CA_side, A_C, C_A, C_CA = Polygon(A, C, 3)

# Lines from triangle vertices to opposite external vertices
line1 = Line(C, C_AB)
line2 = Line(A, C_BC)
line3 = Line(B, C_CA)

# Fermat point = intersection of any two
F = Intersect(line1, line2)

# Style: keep concurrence lines visible
style(line1, line2, line3, stroke="color.accent", stroke_width_px="line_width.bold")
style(F, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$F$")

# Hide helper polygon boundaries (optional, keep faces for clarity)
hide(tri_AB, tri_BC, tri_CA)

# Show triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
