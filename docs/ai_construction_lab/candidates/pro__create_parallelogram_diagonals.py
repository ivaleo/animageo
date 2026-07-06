# Given three vertices A, B, C of a parallelogram
A = Point(-2, 1)
B = Point(1, 2)
C = Point(2, -1)

# Construct the fourth vertex D using vector addition: D = A + (C - B)
D = A + (C - B)

# Build the parallelogram sides
AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Construct diagonals and their intersection
AC = Segment(A, C)
BD = Segment(B, D)
O = Intersect(AC, BD)

# Style: main sides in main color, diagonals as auxiliary, intersection point bold
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")
style(AC, BD, stroke="color.aux", stroke_width_px="line_width.aux")
style(O, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Ensure vertex labels are visible
style(A, B, C, D, label_visible=True)
