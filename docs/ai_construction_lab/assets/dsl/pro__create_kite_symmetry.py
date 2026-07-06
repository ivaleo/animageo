# Дельтоид ABCD с осью симметрии AC
# Строим две пары равных смежных сторон: AB = AD и CB = CD

# Свободные точки
A = Point(0, 0)
C = Point(4, 0)

# Ось симметрии — прямая AC
axis = Line(A, C)

# Точка B — свободная точка с одной стороны от оси
B = Point(1, 2)

# Точка D — отражение B относительно оси AC
D = Reflect(B, axis)

# Стороны дельтоида
AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)

# Диагонали
AC = Segment(A, C)
BD = Segment(B, D)

# Стилизация
style(A, B, C, D, label_visible=True)
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")
style(AC, stroke="color.accent", stroke_width_px="line_width.bold")
style(BD, stroke="color.aux", stroke_width_px="line_width.aux")

# Отметки равенства сторон: AB = AD и CB = CD
style(AB, DA, tick_count=1)
style(BC, CD, tick_count=2)

# Прямой угол между диагоналями (свойство дельтоида)
O = Intersect(AC, BD)
right_angle = Angle(A, O, D)
style(right_angle, right_angle_marker=True, right_angle_size_px="angle_radius.right")

# Скрываем вспомогательную ось
hide(axis)
