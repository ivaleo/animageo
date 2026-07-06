# Triangle ABC
A = Point(-3, -1)
B = Point(3, -1)
C = Point(0, 4)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(A, B, C, label_visible=True)

# Midpoint of AB
M = Midpoint(A, B)
style(M, label_visible=True)

# Median from C to M
CM = Segment(C, M)
style(CM, stroke="color.accent", stroke_width_px="line_width.bold")

# Centroid G (intersection of medians)
N = Midpoint(B, C)
BN = Segment(B, N)
G = Intersect(CM, BN)
style(G, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Hide the second median (only needed to find G)
hide(BN, N)

# Subdivide CM into CG and GM to show 2:1 ratio
CG = Segment(C, G)
GM = Segment(G, M)
style(CG, stroke="color.accent", stroke_width_px="line_width.bold")
style(GM, stroke="color.accent", stroke_width_px="line_width.bold")

# Mark equal halves on AB (AM = MB)
AM = Segment(A, M)
MB = Segment(M, B)
style(AM, MB, stroke="color.main", stroke_width_px="line_width.main", tick_count=1)

# Ratio labels
style(CG, label_visible=True, label_text="$2x$")
style(GM, label_visible=True, label_text="$x$")

# Hide the original full median segment to avoid double drawing
hide(CM)
