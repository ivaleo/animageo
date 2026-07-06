A = Point(0, 0)
B = Point(6, 0)
C = Point(2, 4)
tri, AB, BC, CA = Polygon(A, B, C)

# Internal angle bisector at A
bis_A = AngularBisector(B, A, C)

# External angle bisector at B (perpendicular to internal bisector at B)
bis_B_int = AngularBisector(A, B, C)
ext_B = PerpendicularLine(B, bis_B_int)

# Excenter I_A opposite A
I_A = Intersect(bis_A, ext_B)

# Foot of perpendicular from I_A to BC (tangency point on BC)
foot_line = PerpendicularLine(I_A, BC)
T = Intersect(foot_line, BC)

# Excircle radius segment
r_seg = Segment(I_A, T)

# Excircle
excircle = Circle(I_A, T)

# Mark right angle at tangency
right_angle = Angle(I_A, T, B)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Style
style(A, B, C, label_visible=True)
style(I_A, label_visible=True, label_text="$I_A$")
style(T, label_visible=True, label_text="$T$")
style(excircle, stroke="color.accent", stroke_width_px="line_width.main")
style(r_seg, stroke="color.aux", stroke_width_px="line_width.aux")
hide(bis_A, bis_B_int, ext_B, foot_line)
