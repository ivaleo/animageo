# Define the base diameter points
A = Point(-4, 0)
B = Point(4, 0)
C = Point(0, 0)

# Draw the base diameter segment
AB = Segment(A, B)
AC = Segment(A, C)
CB = Segment(C, B)

# Construct the three semicircles on the diameter subsegments
outer = Semicircle(A, B)
left = Semicircle(A, C)
right = Semicircle(C, B)

# Style the construction
style(A, B, C, label_visible=True)
style(AB, stroke="color.main", stroke_width_px="line_width.main")
style(AC, CB, stroke="color.aux", stroke_width_px="line_width.aux")
style(outer, stroke="color.main", stroke_width_px="line_width.main")
style(left, right, stroke="color.aux", stroke_width_px="line_width.aux")
