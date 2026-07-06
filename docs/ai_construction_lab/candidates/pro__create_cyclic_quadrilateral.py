# Given points on a circle
O = Point(0, 0)
A = Point(2, 0)
B = Rotate(A, 2 * pi / 5, O)
C = Rotate(B, 2 * pi / 5, O)
D = Rotate(C, 2 * pi / 5, O)

# Circle and quadrilateral
circle = Circle(O, A)
quad, AB, BC, CD, DA = Polygon(A, B, C, D)

# Style the circle and quadrilateral
style(circle, stroke="color.aux", stroke_width_px="line_width.aux")
style(quad, fill="color.aux", fill_opacity=0.1, stroke="color.main", stroke_width_px="line_width.main")

# Mark opposite angles
ang_ABC = Angle(A, B, C)
ang_CDA = Angle(C, D, A)
ang_BCD = Angle(B, C, D)
ang_DAB = Angle(D, A, B)

style(ang_ABC, ang_CDA, arc_size_px="angle_radius.bold", tick_count=1, stroke="color.accent", stroke_width_px="line_width.bold")
style(ang_BCD, ang_DAB, arc_size_px="angle_radius.bold", tick_count=2, stroke="color.accent", stroke_width_px="line_width.bold")

# Labels
style(A, B, C, D, label_visible=True)
style(O, label_visible=False)
