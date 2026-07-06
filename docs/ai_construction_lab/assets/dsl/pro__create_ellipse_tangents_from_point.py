# Ellipse with two tangents from external point P

# Ellipse: foci F1, F2, semi-major axis length 3
F1 = Point(-2, 0)
F2 = Point(2, 0)
ellipse = Ellipse(F1, F2, 3)

# External point P
P = Point(4, 2)

# Tangents from P to ellipse
t1, t2 = Tangent(P, ellipse)

# Tangent points
T1 = Intersect(t1, ellipse)
T2 = Intersect(t2, ellipse)

# Visible tangent segments
PT1 = Segment(P, T1)
PT2 = Segment(P, T2)

# Hide infinite tangent lines
hide(t1, t2)

# Style
style(ellipse, stroke="color.main", stroke_width_px="line_width.main")
style(F1, F2, fill="color.main", size_px="point_size.main", label_visible=True)
style(F1, label_text="$F_1$")
style(F2, label_text="$F_2$")
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(T1, T2, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(T1, label_text="$T_1$")
style(T2, label_text="$T_2$")
style(PT1, PT2, stroke="color.accent", stroke_width_px="line_width.bold")
