A = Point(-2, 0)
B = Point(2, 0)

# Internal division point M on AB with AM:MB = 2:1
M = A + (2.0 / 3.0) * (B - A)

# External division point N on line AB with AN:NB = 2:1 (external)
N = A + 2.0 * (B - A)

# Apollonius circle has diameter MN
O = Midpoint(M, N)
circle = Circle(O, M)

# Mark the given points and the circle
style(A, B, fill="color.strong", size_px="point_size.bold", label_visible=True)
style(circle, stroke="color.accent", stroke_width_px="line_width.bold")

# Show the diameter points M and N as auxiliary
style(M, N, fill="color.aux", size_px="point_size.aux", label_visible=True)

# Add a generic point P on the circle to illustrate the ratio
P = Rotate(M, pi / 3, O)
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)

# Draw segments PA and PB
PA = Segment(P, A)
PB = Segment(P, B)
style(PA, PB, stroke="color.accent", stroke_width_px="line_width.bold")

# Mark the ratio with tick marks: PA gets 2 ticks, PB gets 1 tick
style(PA, tick_count=2)
style(PB, tick_count=1)

# Label the ratio near P
style(P, label_text="$P$")
