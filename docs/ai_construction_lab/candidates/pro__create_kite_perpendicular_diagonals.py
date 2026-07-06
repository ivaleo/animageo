# Kite ABCD with AB = AD and CB = CD, showing perpendicular diagonals

# Choose two opposite vertices on the symmetry axis first
A = Point(-2, 0)
C = Point(2, 0)

# Symmetry axis AC
axis = Line(A, C)

# Choose one off-axis vertex
B = Point(0, 2)

# Reflect B across axis to get D, ensuring AB = AD and CB = CD
D = Reflect(B, axis)

# Build kite polygon
kite, AB, BC, CD, DA = Polygon(A, B, C, D)

# Diagonals
AC = Segment(A, C)
BD = Segment(B, D)

# Intersection of diagonals
E = Intersect(AC, BD)

# Mark right angle at intersection
right_angle = Angle(A, E, B)

# Style the kite
style(kite, fill="color.accent", fill_opacity=0.15, stroke="color.main", stroke_width_px="line_width.main")

# Style diagonals
style(AC, BD, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 2")

# Mark right angle
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Label vertices
style(A, B, C, D, label_visible=True)

# Mark adjacent equal side pairs
style(AB, DA, tick_count=1, tick_length_px="tick.main")
style(BC, CD, tick_count=2, tick_length_px="tick.main")

# Hide axis helper
hide(axis)
