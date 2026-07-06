# Given three vertices of a parallelogram
A = Point(-3, 2)
B = Point(1, 2)
C = Point(2, -1)

# Construct the fourth vertex D using vector addition: D = A + (C - B)
D = A + (C - B)

# Build the parallelogram sides
AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Style the sides
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")

# Construct diagonals
AC = Segment(A, C)
BD = Segment(B, D)
style(AC, BD, stroke="color.aux", stroke_width_px="line_width.aux")

# Intersection point of diagonals
O = Intersect(AC, BD)
style(O, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Split diagonals at O to mark equal halves
AO = Segment(A, O)
OC = Segment(O, C)
BO = Segment(B, O)
OD = Segment(O, D)

# Hide the full diagonal segments to avoid double drawing
hide(AC, BD)

# Style the half-diagonals as auxiliary but visible
style(AO, OC, BO, OD, stroke="color.aux", stroke_width_px="line_width.aux")

# Mark equal halves with tick_count: AO=OC and BO=OD
style(AO, OC, tick_count=1)
style(BO, OD, tick_count=2)

# Ensure vertex labels are visible
style(A, B, C, D, label_visible=True)
