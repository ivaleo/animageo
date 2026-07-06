A = Point(0, 0)
B = Point(4, 0)

# Choose an independent shared radius larger than half of AB so A and B are not on the opposite circles
r = 3.5

cA = Circle(A, r)
cB = Circle(B, r)

C, D = Intersect(cA, cB)

# Build the rhombus sides explicitly
AC = Segment(A, C)
CB = Segment(C, B)
BD = Segment(B, D)
DA = Segment(D, A)

# Style the rhombus sides as main geometry
style(AC, CB, BD, DA, stroke="color.main", stroke_width_px="line_width.main")

# Mark all four sides equal with the same tick_count
style(AC, CB, BD, DA, tick_count=1)

# Hide the construction circles
hide(cA, cB)

# Keep vertices visible and labeled
style(A, B, C, D, label_visible=True, fill="color.main", size_px="point_size.main")

# Optionally draw diagonal AB as auxiliary (it is the given diagonal)
AB_seg = Segment(A, B)
style(AB_seg, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 2")

# Notes: The rhombus is constructed from two equal circles with centers A and B and an independent radius 3.5.
# The diagonal AB is shown as a dashed auxiliary segment.
# All four sides are marked equal with one tick.
