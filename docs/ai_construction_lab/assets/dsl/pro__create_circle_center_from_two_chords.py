# Given circle with two chords AB and CD
# Free points for the circle center and a point on the circle
O_hidden = Point(0, 0)
P = Point(3, 0)
circle = Circle(O_hidden, P)

# Chord endpoints on the circle (constructed by rotating P)
A = Rotate(P, 0.8, O_hidden)
B = Rotate(P, 2.3, O_hidden)
C = Rotate(P, 3.9, O_hidden)
D = Rotate(P, 5.1, O_hidden)

# Chords
AB = Segment(A, B)
CD = Segment(C, D)

# Perpendicular bisectors of the chords
perp_bis_AB = PerpendicularBisector(A, B)
perp_bis_CD = PerpendicularBisector(C, D)

# Intersection of the perpendicular bisectors is the center
O = Intersect(perp_bis_AB, perp_bis_CD)

# Style the found center
style(O, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="O")

# Hide the original hidden center and its helper point
hide(O_hidden, P)

# Style chords and perpendicular bisectors
style(AB, CD, stroke="color.main", stroke_width_px="line_width.main")
style(perp_bis_AB, perp_bis_CD, stroke="color.aux", stroke_width_px="line_width.aux")

# Mark midpoints of chords (optional, for clarity)
M_AB = Midpoint(A, B)
M_CD = Midpoint(C, D)
style(M_AB, M_CD, fill="color.aux", size_px="point_size.aux", label_visible=False)

# Right angle markers at midpoints
right_angle_AB = Angle(A, M_AB, O)
right_angle_CD = Angle(C, M_CD, O)
style(right_angle_AB, right_angle_CD, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Keep circle visible
style(circle, stroke="color.main", stroke_width_px="line_width.main")
