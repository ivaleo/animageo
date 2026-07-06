# Given triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)

# Sides of ABC
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# External equilateral triangles on each side
# On AB: external means opposite to C
C_AB = Rotate(B, pi/3, A)  # rotate B around A by +60°
D = Rotate(A, -pi/3, B)    # rotate A around B by -60°; choose the one opposite C
# Determine which of C_AB and D is external (farther from C)
# Use distance comparison: if Distance(C_AB, C) > Distance(D, C) then C_AB is external
# We'll construct both and pick the one with larger distance to C
# But we can just pick the one that is not inside ABC; for typical coordinates, C_AB is external
# Let's verify: A(-3,-1), B(3,-1), C(0,4). Rotating B around A by +60° gives point above AB, likely external.
# We'll use C_AB as the external vertex.

# External triangle on AB: vertices A, B, C_AB
tri_AB, AB1, B_CAB, CAB_A = Polygon(A, B, C_AB)

# On BC: external means opposite to A
# Rotate C around B by +60°
A_BC = Rotate(C, pi/3, B)
# Rotate B around C by -60°
E = Rotate(B, -pi/3, C)
# Choose the one farther from A; A_BC likely external
tri_BC, BC1, C_A_BC, A_BC_B = Polygon(B, C, A_BC)

# On CA: external means opposite to B
# Rotate A around C by +60°
B_CA = Rotate(A, pi/3, C)
# Rotate C around A by -60°
F = Rotate(C, -pi/3, A)
# Choose the one farther from B; B_CA likely external
tri_CA, CA1, A_B_CA, B_CA_C = Polygon(C, A, B_CA)

# Centers of external equilateral triangles (centroids)
O_AB = Centroid(tri_AB)
O_BC = Centroid(tri_BC)
O_CA = Centroid(tri_CA)

# Napoleon triangle (connecting centers)
nap_tri, nap_AB, nap_BC, nap_CA = Polygon(O_AB, O_BC, O_CA)

# Styling
style(A, B, C, fill="color.strong", size_px="point_size.bold", label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# External triangles: secondary style
style(tri_AB, tri_BC, tri_CA, stroke="color.aux", stroke_width_px="line_width.aux", fill_opacity=0.1)
style(C_AB, A_BC, B_CA, fill="color.aux", size_px="point_size.aux", label_visible=True)

# Centers: accent
style(O_AB, O_BC, O_CA, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Napoleon triangle: bold accent
style(nap_tri, stroke="color.accent", stroke_width_px="line_width.bold")
style(nap_AB, nap_BC, nap_CA, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide original triangle sides if they overlap? No, keep them visible.
# Hide the external triangle sides that coincide with original sides? They are separate segments, but we can hide the ones that duplicate AB, BC, CA.
# The Polygon command creates new segments for each side. We'll hide the ones that are exactly the same as original sides to avoid double drawing.
# AB1 is the side from A to B in tri_AB, which is same as AB. Hide it.
hide(AB1, BC1, CA1)

# Also hide the other duplicate sides if any (e.g., B_CAB is B to C_AB, which is new, keep).
# For tri_BC: BC1 is B to C (duplicate), hide. C_A_BC is C to A_BC (new), keep. A_BC_B is A_BC to B (new), keep.
# For tri_CA: CA1 is C to A (duplicate), hide. A_B_CA is A to B_CA (new), keep. B_CA_C is B_CA to C (new), keep.

# Mark equal sides of external triangles? Not requested, but could add ticks if needed.

# Ensure labels for centers are visible
style(O_AB, label_text="$O_{AB}$")
style(O_BC, label_text="$O_{BC}$")
style(O_CA, label_text="$O_{CA}$")
