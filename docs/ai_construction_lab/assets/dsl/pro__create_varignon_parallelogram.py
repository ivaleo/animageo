# Произвольный четырёхугольник ABCD
A = Point(-3, 2)
B = Point(2, 3)
C = Point(3, -1)
D = Point(-2, -2)

# Стороны четырёхугольника
AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Середины сторон
M_AB = Midpoint(A, B)
M_BC = Midpoint(B, C)
M_CD = Midpoint(C, D)
M_DA = Midpoint(D, A)

# Параллелограмм Вариньона
varignon, V_AB, V_BC, V_CD, V_DA = Polygon(M_AB, M_BC, M_CD, M_DA)

# Стилизация
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")
style(varignon, stroke="color.accent", stroke_width_px="line_width.bold", fill="color.accent", fill_opacity=0.15)
style(M_AB, M_BC, M_CD, M_DA, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(A, B, C, D, label_visible=True)

# Отметки равенства половинок сторон (для наглядности)
# Половины AB
AM_AB = Segment(A, M_AB)
M_AB_B = Segment(M_AB, B)
style(AM_AB, M_AB_B, stroke_width_px=0, tick_count=1)

# Половины BC
BM_BC = Segment(B, M_BC)
M_BC_C = Segment(M_BC, C)
style(BM_BC, M_BC_C, stroke_width_px=0, tick_count=2)

# Половины CD
CM_CD = Segment(C, M_CD)
M_CD_D = Segment(M_CD, D)
style(CM_CD, M_CD_D, stroke_width_px=0, tick_count=3)

# Половины DA
DM_DA = Segment(D, M_DA)
M_DA_A = Segment(M_DA, A)
style(DM_DA, M_DA_A, stroke_width_px=0, tick_count=4)
