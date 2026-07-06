# Triangle ABC
A = Point(-3, 0)
B = Point(3, 0)
C = Point(0, 4)
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(A, B, C, label_visible=True)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Line intersecting AB, AC, and extension of BC
# Choose a line that crosses AB and AC inside the segments, and meets BC extended beyond C
# Define line through two points: one on AB, one on AC
D = Point(-1.5, 0)  # on AB
E = Point(0, 2)     # on AC
line_DE = Line(D, E)
style(line_DE, stroke="color.accent", stroke_width_px="line_width.bold")

# Intersection with BC extension: extend BC beyond C
# BC is from B(3,0) to C(0,4). Extend beyond C: direction C - B = (-3,4)
# Parameter t > 1 gives point beyond C. Choose t=2 for a point on the extension.
C_ext = C + (C - B)  # point beyond C
line_BC_ext = Line(B, C_ext)  # line through B and C_ext (same as line BC)
F = Intersect(line_DE, line_BC_ext)
style(F, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Mark D and E on the segments
style(D, E, label_visible=True, fill="color.accent", size_px="point_size.bold")

# Hide helper line for BC extension
hide(line_BC_ext)

# Draw segments for the intersection points on the triangle sides
AD = Segment(A, D)
DB = Segment(D, B)
AE = Segment(A, E)
EC = Segment(E, C)
CF = Segment(C, F)  # part of BC extension
style(AD, DB, AE, EC, stroke="color.aux", stroke_width_px="line_width.aux")
style(CF, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide original BC segment to avoid overlap with CF? No, keep BC visible as main triangle side.
# CF is drawn on top, so it will be visible.

# Label the line
style(line_DE, label_visible=True, label_text="l")
