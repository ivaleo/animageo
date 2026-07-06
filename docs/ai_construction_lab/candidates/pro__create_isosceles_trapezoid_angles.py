# Isosceles trapezoid ABCD with AB || CD, AD = BC
# Base AB longer, base CD shorter
A = Point(-4, 0)
B = Point(4, 0)
# Choose a height and offset for the top base
h = 3
offset = 2
D = Point(-2, h)
C = Point(2, h)

# Sides
AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Mark equal legs with same tick count
style(DA, BC, stroke="color.main", stroke_width_px="line_width.main")
style(DA, BC, tick_count=1)

# Mark equal base angles
# At base AB: angle DAB and angle CBA are equal
ang_DAB = Angle(D, A, B)
ang_CBA = Angle(C, B, A)
style(ang_DAB, ang_CBA, arc_size_px="angle_radius.main", tick_count=1)

# At base CD: angle ADC and angle BCD are equal
ang_ADC = Angle(A, D, C)
ang_BCD = Angle(B, C, D)
style(ang_ADC, ang_BCD, arc_size_px="angle_radius.main", tick_count=2)

# Labels
style(A, B, C, D, label_visible=True)
style(AB, CD, stroke="color.main", stroke_width_px="line_width.main")
