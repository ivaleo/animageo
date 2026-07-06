O = Point(0, 0)
A = Point(2.5, 0)
circle = Circle(O, A)
B = Rotate(A, 2.0943951023931953, O)
AB = Segment(A, B)
# Tangent at A: rotate radius OA by 90 degrees to get direction
T = Rotate(O, 1.5707963267948966, A)
tangent = Line(A, T)
# Inscribed angle ACB: choose C on circle (different from A, B)
C = Rotate(A, 4.1887902047863905, O)
CA = Segment(C, A)
CB = Segment(C, B)
# Mark right angle between radius OA and tangent
right_angle = Angle(O, A, T)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")
# Mark inscribed angle ACB
inscribed = Angle(A, C, B)
style(inscribed, arc_size_px="angle_radius.main", tick_count=1)
# Mark tangent-chord angle between tangent and chord AB
tangent_chord = Angle(T, A, B)
style(tangent_chord, arc_size_px="angle_radius.main", tick_count=1)
# Style elements
style(A, B, C, label_visible=True)
style(O, label_visible=False)
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(AB, stroke="color.main", stroke_width_px="line_width.main")
style(tangent, stroke="color.accent", stroke_width_px="line_width.bold")
style(CA, CB, stroke="color.aux", stroke_width_px="line_width.aux")
hide(T)
