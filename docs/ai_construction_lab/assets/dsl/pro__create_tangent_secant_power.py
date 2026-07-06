# Теорема о касательной и секущей
# Дано: точка P вне окружности, касательная PT и секущая PAB

# Окружность с центром O и радиусом 2
O = Point(0, 0)
A0 = Point(2, 0)
circle = Circle(O, A0)

# Точка P вне окружности
P = Point(4, 1)

# Касательная из P к окружности
t1, t2 = Tangent(P, circle)
T = Intersect(t1, circle)
PT = Segment(P, T)

# Секущая через P, пересекающая окружность в A и B
# Проведем прямую через P и некоторую точку на окружности
Q = Rotate(A0, pi/3, O)  # точка на окружности
secant_line = Line(P, Q)
A, B = Intersect(secant_line, circle)
PA = Segment(P, A)
PB = Segment(P, B)

# Стилизация
style(circle, stroke="color.main", stroke_width_px="line_width.main")
style(O, fill="color.main", size_px="point_size.main", label_visible=True)
style(P, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(T, fill="color.accent", size_px="point_size.bold", label_visible=True)
style(A, fill="color.aux", size_px="point_size.main", label_visible=True)
style(B, fill="color.aux", size_px="point_size.main", label_visible=True)
style(PT, stroke="color.accent", stroke_width_px="line_width.bold")
style(PA, stroke="color.aux", stroke_width_px="line_width.main")
style(PB, stroke="color.aux", stroke_width_px="line_width.main")

# Скрыть вспомогательные линии
hide(t1, t2, secant_line, Q)

# Показать радиусы к точкам касания и пересечения для наглядности
OT = Segment(O, T)
OA = Segment(O, A)
OB = Segment(O, B)
style(OT, OA, OB, stroke="color.aux", stroke_width_px="line_width.aux", stroke_dasharray="4 2")

# Подпись теоремы
style(PT, label_text="$PT^2 = PA \\cdot PB$", label_visible=True, label_mode="caption")
