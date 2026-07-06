O = Point(0, 0)
circle = Circle(O, 4)
P = Point(-6, 0)

# First secant line through P
A1 = Point(-3.5, 1.5)
line1 = Line(P, A1)
I1, I2 = Intersect(line1, circle)

# Second secant line through P
B1 = Point(-3.5, -1.5)
line2 = Line(P, B1)
I3, I4 = Intersect(line2, circle)

# Visible secant segments
seg1 = Segment(P, I2)
seg2 = Segment(P, I4)

# Label intersection points with math subscripts
style(I1, label_visible=True, label_text="$A_1$")
style(I2, label_visible=True, label_text="$B_1$")
style(I3, label_visible=True, label_text="$C_1$")
style(I4, label_visible=True, label_text="$D_1$")

# Style secant segments
style(seg1, seg2, stroke="color.accent", stroke_width_px="line_width.bold")

# Hide helper lines
hide(line1, line2)

# Show external point P
style(P, label_visible=True, fill="color.strong", size_px="point_size.bold")
