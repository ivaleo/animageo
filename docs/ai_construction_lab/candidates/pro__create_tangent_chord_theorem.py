# Given circle and points
O = Point(0, 0)
A = Point(2, 0)
B = Point(-1.5, 1.5)
C = Point(0.5, 2.2)
circle = Circle(O, A)

# Chord AB
AB = Segment(A, B)

# Tangent at A
tangent_line = Tangent(A, circle)

# Inscribed angle ACB
CA = Segment(C, A)
CB = Segment(C, B)
angle_ACB = Angle(A, C, B)

# Angle between tangent and chord (at A)
# The tangent line is infinite; we need a ray along the tangent for the angle.
# Choose a point T on the tangent line away from A to define the ray.
# Use a point on the tangent line: rotate A around O by 90 degrees to get a direction.
T = Rotate(A, pi/2, O)
# Ensure T lies on the tangent line (it does by construction).
ray_AT = Ray(A, T)
angle_tangent_chord = Angle(B, A, T)

# Styling
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(AB, stroke="color.main", stroke_width_px="line_width.main")
style(CA, CB, stroke="color.aux", stroke_width_px="line_width.aux")
style(tangent_line, stroke="color.accent", stroke_width_px="line_width.bold")
style(ray_AT, stroke="color.accent", stroke_width_px="line_width.bold")
style(angle_ACB, arc_size_px="angle_radius.main", tick_count=1)
style(angle_tangent_chord, arc_size_px="angle_radius.main", tick_count=1)

# Labels
style(A, B, C, O, label_visible=True)
style(angle_ACB, label_visible=True, label_text="$\\angle ACB$")
style(angle_tangent_chord, label_visible=True, label_text="$\\theta$")

# Hide helper point T
hide(T)
