# Triangle ABC with three cevians through an interior point P

# Free vertices of the triangle
A = Point(-3, -2)
B = Point(3, -2)
C = Point(0, 4)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)

# Interior point P (free, placed inside the triangle)
P = Point(0, 0)

# Cevians: lines from each vertex through P, intersected with the opposite side
line_AP = Line(A, P)
line_BP = Line(B, P)
line_CP = Line(C, P)

D = Intersect(line_AP, BC)
E = Intersect(line_BP, CA)
F = Intersect(line_CP, AB)

# Visible cevian segments
AD = Segment(A, D)
BE = Segment(B, E)
CF = Segment(C, F)

# Style: triangle sides as main, cevians as accent, point P highlighted
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")
style(AD, BE, CF, stroke="color.accent", stroke_width_px="line_width.bold")
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Hide infinite helper lines
hide(line_AP, line_BP, line_CP)

# Ensure vertex labels are visible
style(A, B, C, label_visible=True)
style(D, E, F, label_visible=True, fill="color.aux", size_px="point_size.aux")
