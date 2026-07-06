# Free points for the square
A = Point(0, 0)
B = Point(3, 0)

# Construct the square on AB
square, AB, BC, CD, DA, C, D = Polygon(A, B, 4)

# Diagonals
AC = Segment(A, C)
BD = Segment(B, D)

# Intersection point of diagonals
O = Intersect(AC, BD)

# Style the square sides
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")

# Style the diagonals
style(AC, BD, stroke="color.aux", stroke_width_px="line_width.aux")

# Style the intersection point
style(O, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Ensure vertex labels are visible
style(A, B, C, D, label_visible=True)
