# Given circle and two chords
O_approx = Point(0, 0)
A = Point(-2.1, 1.7)
B = Point(2.1, 1.7)
C = Point(1.5, -2.0)
D = Point(-1.8, -1.5)
circle = Circle(O_approx, A)

# Chords
AB = Segment(A, B)
CD = Segment(C, D)

# Perpendicular bisectors
perp_bis_AB = PerpendicularBisector(A, B)
perp_bis_CD = PerpendicularBisector(C, D)

# Center as intersection
O = Intersect(perp_bis_AB, perp_bis_CD)

# Styling
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(AB, CD, stroke="color.main", stroke_width_px="line_width.main")
style(perp_bis_AB, perp_bis_CD, stroke="color.aux", stroke_width_px="line_width.aux")
style(O, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$O$")
style(A, B, C, D, label_visible=True)
hide(O_approx)
