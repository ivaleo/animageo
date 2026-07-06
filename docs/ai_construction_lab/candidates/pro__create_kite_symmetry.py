# Дельтоид ABCD с осью симметрии AC
A = Point(0, 0)
C = Point(4, 0)
# Ось симметрии — прямая AC
axis = Line(A, C)
# Свободная точка B с одной стороны от оси
B = Point(1, 2)
# D — отражение B относительно оси AC
D = Reflect(B, axis)
# Стороны дельтоида
AB = Segment(A, B)
BC = Segment(B, C)
CD = Segment(C, D)
DA = Segment(D, A)
# Стилизация: основная фигура
style(AB, BC, CD, DA, stroke="color.main", stroke_width_px="line_width.main")
# Метки равных сторон: AB = AD и BC = CD
style(AB, DA, tick_count=1)
style(BC, CD, tick_count=2)
# Видимость точек и подписи
style(A, B, C, D, label_visible=True, fill="color.main", size_px="point_size.main")
# Ось симметрии — вспомогательная
style(axis, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 4")
hide(axis)
