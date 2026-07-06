# Regular hexagon inscribed in a circle
O = Point(0, 0)
A = Point(3, 0)
circle = Circle(O, A)

# First side AB: B is the next vertex on the circle, 60° CCW from A
B = Rotate(A, pi/3, O)

# Build the regular hexagon from side AB
hexagon, AB, BC, CD, DE, EF, FA, C, D, E, F = Polygon(A, B, 6)

# Style the hexagon boundary as main figure
style(hexagon, stroke="color.main", stroke_width_px="line_width.main")

# Mark equal sides: all six sides are equal, use tick_count=1
style(AB, BC, CD, DE, EF, FA, tick_count=1)

# Draw and mark equal radii: OA, OB, OC, OD, OE, OF
OA = Segment(O, A)
OB = Segment(O, B)
OC = Segment(O, C)
OD = Segment(O, D)
OE = Segment(O, E)
OF = Segment(O, F)
style(OA, OB, OC, OD, OE, OF, stroke="color.aux", stroke_width_px="line_width.aux", tick_count=2)

# Style the circle as auxiliary
style(circle, stroke="color.aux", stroke_width_px="line_width.aux")

# Label vertices
style(A, B, C, D, E, F, label_visible=True)
style(O, label_visible=True)
