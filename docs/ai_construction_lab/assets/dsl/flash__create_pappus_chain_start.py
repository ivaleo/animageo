# Arbelos with first two Pappus chain circles
# Outer semicircle on AB, left semicircle on AC, right semicircle on CB
A = Point(-4, 0)
C = Point(-1, 0)
B = Point(4, 0)

outer = Semicircle(A, B)
left = Semicircle(A, C)
right = Semicircle(C, B)

AB = Segment(A, B)
AC = Segment(A, C)
CB = Segment(C, B)

# Arbelos radii
R = 4  # outer radius (AB/2)
r1 = 1.5  # left radius (AC/2)
r2 = 2.5  # right radius (CB/2)

# Center of outer semicircle
O = Point(0, 0)

# First Pappus circle (n=1): radius = (r1*r2*R) / (r1^2 + r1*r2 + r2^2) ???
# Standard formula: for chain circles tangent to left and right semicircles and outer semicircle
# Using Descartes circle theorem or known formula:
# For arbelos with radii r1, r2, the nth Pappus circle has radius r_n = (r1*r2*R) / (n^2 * (r1+r2)^2 + r1*r2)
# Actually simpler: r_n = (r1*r2*R) / (n^2 * (r1+r2)^2 + r1*r2) ???
# Let's use known result: r_n = (r1*r2) / (n^2 * (r1+r2) + r1*r2/R) ???
# Better: use formula from geometry: r_n = (r1*r2*R) / (n^2 * (r1+r2)^2 + r1*r2)
# But R = r1+r2, so r_n = (r1*r2*(r1+r2)) / (n^2 * (r1+r2)^2 + r1*r2) = (r1*r2) / (n^2*(r1+r2) + r1*r2/(r1+r2))
# Actually simpler: r_n = (r1*r2) / (n^2*(r1+r2) + r1*r2/(r1+r2))? Let's compute numerically.

# Use known formula: r_n = (r1*r2) / (n^2*(r1+r2) + r1*r2/(r1+r2))? No.
# Standard: r_n = (r1*r2*R) / (n^2 * (r1+r2)^2 + r1*r2) with R = r1+r2 => r_n = (r1*r2*(r1+r2)) / (n^2*(r1+r2)^2 + r1*r2) = (r1*r2) / (n^2*(r1+r2) + r1*r2/(r1+r2))
# Let's compute directly with numbers.

r1_val = 1.5
r2_val = 2.5
R_val = r1_val + r2_val  # 4.0

# For n=1:
n1 = 1
r_n1 = (r1_val * r2_val * R_val) / (n1**2 * (r1_val + r2_val)**2 + r1_val * r2_val)
# = (1.5*2.5*4) / (1*16 + 3.75) = 15 / 19.75 ≈ 0.7595

# For n=2:
n2 = 2
r_n2 = (r1_val * r2_val * R_val) / (n2**2 * (r1_val + r2_val)**2 + r1_val * r2_val)
# = 15 / (4*16 + 3.75) = 15 / 67.75 ≈ 0.2214

# Center x-coordinate: x_n = (r2 - r1) + 2*n*sqrt(r1*r2) * (something)?
# Actually center of nth Pappus circle: x_n = (r2 - r1) + 2*n*sqrt(r1*r2) * (r1+r2)/?
# Known: center x-coordinate from midpoint of AC? Let's use formula:
# x_n = (r2 - r1) + 2*n*sqrt(r1*r2) * (r1+r2)/?
# Better: use coordinate geometry: center of left semicircle at (-r1,0), right at (r2,0)
# For circle tangent to left, right, and outer, the center (x_n, y_n) satisfies:
# distance to left center = r1 + r_n, to right center = r2 + r_n, to outer center = R - r_n
# Solve: (x_n + r1)^2 + y_n^2 = (r1 + r_n)^2
# (x_n - r2)^2 + y_n^2 = (r2 + r_n)^2
# Subtract: (x_n + r1)^2 - (x_n - r2)^2 = (r1+r_n)^2 - (r2+r_n)^2
# => (x_n^2+2r1 x_n+r1^2) - (x_n^2-2r2 x_n+r2^2) = r1^2+2r1 r_n+r_n^2 - r2^2-2r2 r_n - r_n^2
# => 2r1 x_n + r1^2 + 2r2 x_n - r2^2 = r1^2 - r2^2 + 2r_n(r1 - r2)
# => 2(r1+r2)x_n = 2r_n(r1 - r2) => x_n = r_n*(r1 - r2)/(r1+r2)
# Then y_n = sqrt((r1+r_n)^2 - (x_n + r1)^2)

# Compute for n=1:
x1 = r_n1 * (r1_val - r2_val) / (r1_val + r2_val)  # = 0.7595 * (-1)/4 = -0.1899
y1 = sqrt((r1_val + r_n1)**2 - (x1 + r1_val)**2)

# Compute for n=2:
x2 = r_n2 * (r1_val - r2_val) / (r1_val + r2_val)  # = 0.2214 * (-1)/4 = -0.05535
y2 = sqrt((r1_val + r_n2)**2 - (x2 + r1_val)**2)

# Create centers and circles
O1 = Point(x1, y1)
O2 = Point(x2, y2)

# Create circles with computed radii
c1 = Circle(O1, r_n1)
c2 = Circle(O2, r_n2)

# Style: arbelos semicircles and baseline visible, chain circles accented
style(outer, left, right, stroke="color.main", stroke_width_px="line_width.main")
style(AB, AC, CB, stroke="color.aux", stroke_width_px="line_width.aux")
style(c1, c2, stroke="color.accent", stroke_width_px="line_width.bold")
hide(O, O1, O2)
