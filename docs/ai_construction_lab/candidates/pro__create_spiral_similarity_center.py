# Two intersecting circles; their shared points come from Intersect(c1, c2)
O1 = Point(-1.5, 0)
O2 = Point(1.5, 0)
seed = Point(0, 2)
c1 = Circle(O1, seed)
c2 = Circle(O2, seed)
S, T = Intersect(c1, c2)

# Chord in c1 through the shared point S
Q1 = Rotate(T, 0.75, O1)
line1 = Line(S, Q1)
A, B = Intersect(line1, c1)

# Corresponding chord in c2 through the same center S
Q2 = Rotate(T, -0.75, O2)
line2 = Line(S, Q2)
C, D = Intersect(line2, c2)

chord1 = Segment(A, B)
chord2 = Segment(C, D)
common_chord = Segment(S, T)

style(c1, c2, stroke="color.main", stroke_width_px="line_width.main")
style(chord1, chord2, stroke="color.accent", stroke_width_px="line_width.bold")
style(common_chord, stroke="color.aux", stroke_width_px="line_width.aux")
style(S, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$S$")
style(T, fill="color.aux", size_px="point_size.main", label_visible=True, label_text="$T$")
style(A, B, C, D, label_visible=True)
hide(O1, O2, seed, Q1, Q2, line1, line2)
