# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(1, 4)

# Sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Centroid G
G = Centroid(A, B, C)
style(G, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Isogonal conjugate of G (symmedian point K)
K = IsogonalConjugation(A, B, C, G)
style(K, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Symmedians: segments from vertices to K
AK = Segment(A, K)
BK = Segment(B, K)
CK = Segment(C, K)
style(AK, BK, CK, stroke="color.accent", stroke_width_px="line_width.bold")

# Vertex labels
style(A, B, C, label_visible=True)
