A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)

triangle, AB, BC, CA = Polygon(A, B, C)
style(triangle, fill_opacity=0.1, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True)

G = Centroid(triangle)
style(G, fill="color.accent", size_px="point_size.bold", label_visible=True)

K = IsogonalConjugation(G, triangle)
style(K, fill="color.accent", size_px="point_size.bold", label_visible=True)

AG = Segment(A, G)
BG = Segment(B, G)
CG = Segment(C, G)
style(AG, BG, CG, stroke="color.aux", stroke_width_px="line_width.aux")

AK = Segment(A, K)
BK = Segment(B, K)
CK = Segment(C, K)
style(AK, BK, CK, stroke="color.aux", stroke_width_px="line_width.aux")

hide(AG, BG, CG, AK, BK, CK)
