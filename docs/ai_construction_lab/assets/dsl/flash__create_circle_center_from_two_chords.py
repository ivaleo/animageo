A = Point(-2, 1)
B = Point(2, -1)
C = Point(-1, -2)
D = Point(3, 2)
circle = Circle(A, B)
C = Intersect(circle, Line(A, B))
D = Intersect(circle, Line(A, B))
# Actually, let's define chord endpoints on the circle properly
# Use two chords: AB and CD, with endpoints on circle
# We'll define A and B as free points on circle, then C and D as rotated versions
O_hidden = Point(0, 0)
A = Point(2, 0)
B = Rotate(A, 2.5, O_hidden)
circle = Circle(O_hidden, A)
C = Rotate(A, 1.2, O_hidden)
D = Rotate(A, 3.8, O_hidden)
# Now construct perpendicular bisectors
mid_AB = Midpoint(A, B)
perp_AB = PerpendicularLine(mid_AB, Line(A, B))
mid_CD = Midpoint(C, D)
perp_CD = PerpendicularLine(mid_CD, Line(C, D))
O = Intersect(perp_AB, perp_CD)
# Mark right angles at midpoints
# For each perpendicular bisector, we need a right angle between the bisector and the chord
# Use a point on the chord to define the angle
# For chord AB, right angle at mid_AB between AB and perp_AB
# Create a point on AB for angle arms
# Actually, we can use the chord segment and the perpendicular line
# But Angle requires three points. Use a point on the chord line.
# Let's create a point on AB (not A or B) for the angle
# Use the midpoint itself as vertex, and two points on the lines
# For perp_AB, we need a point on perp_AB other than mid_AB
# Use O as that point (since O lies on perp_AB)
# For chord AB, use A or B as the other point
angle1 = Angle(A, mid_AB, O)
style(angle1, right_angle_marker=True, right_angle_size_px="angle_radius.right")
angle2 = Angle(C, mid_CD, O)
style(angle2, right_angle_marker=True, right_angle_size_px="angle_radius.right")
# Hide helper center and construction lines
hide(O_hidden, perp_AB, perp_CD)
# Keep circle visible
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(O, label_visible=True, fill="color.accent", size_px="point_size.bold")
style(A, B, C, D, label_visible=True)
# Also show chords
chord_AB = Segment(A, B)
chord_CD = Segment(C, D)
style(chord_AB, chord_CD, stroke="color.main", stroke_width_px="line_width.main")
