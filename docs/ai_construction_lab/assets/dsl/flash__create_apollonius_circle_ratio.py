A = Point(-3, 0)
B = Point(3, 0)
# Choose P on the Apollonius circle: PA:PB = 2:1
# Using internal and external division points
# Internal division: P_int divides AB in ratio 2:1 internally
P_int = A + (2/3) * (B - A)
# External division: P_ext divides AB in ratio 2:1 externally
P_ext = A + 2 * (B - A)
# Apollonius circle has diameter P_int P_ext
O = Midpoint(P_int, P_ext)
apollonius = Circle(O, P_int)
# Show a sample point P on the circle
P = Rotate(P_int, 1.2, O)
# Mark equal ratio: show segments PA and PB
PA = Segment(P, A)
PB = Segment(P, B)
# Label ratio
style(PA, label_visible=True, label_text="$PA$")
style(PB, label_visible=True, label_text="$PB$")
# Add ratio label near P
style(P, label_visible=True, label_text="$P$")
style(A, label_visible=True, label_text="$A$")
style(B, label_visible=True, label_text="$B$")
# Hide construction points
hide(P_int, P_ext, O)
# Add text label for ratio
# Use a point for text placement
T = Point(0, -2)
style(T, label_visible=True, label_text="$PA:PB = 2:1$")
hide(T)
