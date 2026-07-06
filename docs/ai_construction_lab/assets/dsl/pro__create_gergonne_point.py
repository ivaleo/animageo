# Triangle ABC
A = Point(-4, -2)
B = Point(5, -1)
C = Point(0, 5)
style(A, B, C, label_visible=True)

# Triangle sides
AB = Segment(A, B)
BC = Segment(B, C)
CA = Segment(C, A)
style(AB, BC, CA, stroke="color.main", stroke_width_px="line_width.main")

# Incircle
inc = Incircle(A, B, C)
style(inc, stroke="color.accent", stroke_width_px="line_width.bold")

# Incenter
I = Center(inc)
style(I, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$I$")

# Touch points (feet of perpendiculars from I to sides)
perp_AB = PerpendicularLine(I, AB)
perp_BC = PerpendicularLine(I, BC)
perp_CA = PerpendicularLine(I, CA)

D = Intersect(perp_AB, AB)
E = Intersect(perp_BC, BC)
F = Intersect(perp_CA, CA)

style(D, E, F, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(D, label_text="$D$")
style(E, label_text="$E$")
style(F, label_text="$F$")

# Hide perpendicular helpers
hide(perp_AB, perp_BC, perp_CA)

# Right angle markers at touch points
right_D = Angle(A, D, I)
right_E = Angle(B, E, I)
right_F = Angle(C, F, I)
style(right_D, right_E, right_F, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Gergonne point (intersection of lines from vertices to opposite touch points)
line_AD = Line(A, D)
line_BE = Line(B, E)
line_CF = Line(C, F)

Ge = Intersect(line_AD, line_BE)
style(Ge, fill="color.accent", size_px="point_size.bold", label_visible=True, label_text="$Ge$")

# Hide construction lines for Gergonne point
hide(line_AD, line_BE, line_CF)

# Draw segments from vertices to touch points for visibility
AD_seg = Segment(A, D)
BE_seg = Segment(B, E)
CF_seg = Segment(C, F)
style(AD_seg, BE_seg, CF_seg, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 2")
